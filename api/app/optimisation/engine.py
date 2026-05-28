"""
Optimisation engine — DLD §8.

Implements:

    §8.1  Reorder Point + Safety Stock — normal model.
              SS  = z(β) · sqrt(μ_L · σ_d² + μ_d² · σ_L²)
              ROP = μ_d · μ_L + SS
          Demand normality is checked with the Shapiro-Wilk test (scipy);
          when normality is rejected (or scipy is missing), the engine falls
          back to an empirical bootstrap quantile of the simulated lead-time
          demand distribution.  Mathematically equivalent to a normal model
          when demand truly is normal, but robust to lumpy / erratic items.

    §8.3  EOQ — classic Wilson with discount-aware total-cost evaluation:
              EOQ = sqrt( (2 · D · K) / h )
              TC(q) = (D/q) · K + (q/2) · h + D · c(q)

    §4.3  Service-level β routed by criticality:
              non-critical    → 0.95
              critical        → 0.99
              safety-critical → 0.995

The engine takes pure numbers as inputs so it is trivial to unit-test.
Callers (recommendations/generator.py) compose features from Maximo data
into an `OptimisationInput`.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from scipy import stats
    _SCIPY_OK = True
except Exception:
    _SCIPY_OK = False
    np = None  # type: ignore[assignment]
    stats = None  # type: ignore[assignment]


Criticality = Literal["HIGH", "MED", "LOW"]


# ── Public input / output dataclasses ─────────────────────────────────────────

@dataclass
class OptimisationInput:
    item_id: str
    warehouse_id: str
    criticality: Criticality
    # Per-period demand observations (e.g. 24 months of monthly consumption).
    demand_history: Sequence[float] = field(default_factory=list)
    # Lead-time observations in days (from MATRECTRANS / PO history).
    lead_time_days: Sequence[float] = field(default_factory=list)
    # Costs.  unit_cost and order_cost in tenant currency; holding_cost_pct
    # is the annual carrying cost as a fraction of unit cost.
    unit_cost: float = 0.0
    order_cost: float = 75.0
    holding_cost_pct: float = 0.20
    # Quantity-discount price breaks: list of (min_qty, unit_cost_at_that_qty).
    # Empty list → no discount path.
    price_breaks: Sequence[tuple[float, float]] = field(default_factory=list)
    # Optional: existing policy for the delta computation.
    current_rop: Optional[float] = None
    current_ss:  Optional[float] = None
    current_eoq: Optional[float] = None


@dataclass
class OptimisationResult:
    item_id: str
    warehouse_id: str
    # Recommended policy values (rounded to whole units).
    rop: int
    ss:  int
    eoq: int
    # Inputs used (for the rationale block).
    beta: float
    mean_demand_per_period: float
    std_demand_per_period:  float
    mean_lead_time_days:    float
    std_lead_time_days:     float
    # Method chosen by the normality gate.
    ss_method: Literal["normal", "bootstrap"] = "normal"
    # Notes for the rationale text (free-form, kept short).
    notes: list[str] = field(default_factory=list)


# ── Service-level β routing ───────────────────────────────────────────────────

def beta_for(criticality: Criticality) -> float:
    s = get_settings()
    # The "safety-critical" tier is not a Maximo MED — it's a tenant-config
    # extension.  Until that exists, MED maps to the critical β and LOW maps
    # to non-critical β.  HIGH explicitly maps to safety_critical.
    if criticality == "HIGH":
        return s.service_level_safety_critical
    if criticality == "MED":
        return s.service_level_critical
    return s.service_level_non_critical


# ── ROP / SS ──────────────────────────────────────────────────────────────────

def _mean_std(xs: Sequence[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n == 1:
        return m, 0.0
    if _SCIPY_OK:
        arr = np.asarray(xs, dtype=float)
        return float(arr.mean()), float(arr.std(ddof=0))
    var = sum((x - m) ** 2 for x in xs) / n
    return m, var ** 0.5


def _normal_ss_rop(
    *, beta: float, mu_d: float, sigma_d: float, mu_l: float, sigma_l: float,
) -> tuple[float, float]:
    """Closed-form normal model (DLD §8.1)."""
    if _SCIPY_OK:
        z = float(stats.norm.ppf(beta))
    else:
        # Beasley-Springer-Moro is overkill; use a small table for the betas
        # we actually use, falling back to a coarse interpolation otherwise.
        _Z = {0.90: 1.282, 0.95: 1.645, 0.97: 1.881, 0.98: 2.054,
              0.99: 2.326, 0.995: 2.576}
        z = _Z.get(round(beta, 3), 1.645)

    var = mu_l * (sigma_d ** 2) + (mu_d ** 2) * (sigma_l ** 2)
    ss  = z * math.sqrt(max(0.0, var))
    rop = mu_d * mu_l + ss
    return ss, rop


def _bootstrap_ss_rop(
    *, beta: float, demand: Sequence[float], lead: Sequence[float], n_iter: int = 5000,
) -> tuple[float, float]:
    """Empirical bootstrap of lead-time demand distribution."""
    if not _SCIPY_OK:
        # Cheap fallback: a normal approximation using the same stats.
        mu_d, sigma_d = _mean_std(demand)
        mu_l, sigma_l = _mean_std(lead)
        return _normal_ss_rop(beta=beta, mu_d=mu_d, sigma_d=sigma_d,
                              mu_l=mu_l, sigma_l=sigma_l)

    rng = np.random.default_rng(seed=42)
    d_arr = np.asarray(demand, dtype=float)
    l_arr = np.asarray(lead,   dtype=float)
    if d_arr.size == 0 or l_arr.size == 0:
        return 0.0, 0.0

    # Sample lead-time, then sum that many demand draws.  Lead times here
    # are in days but demand is per period — assume 30 days per period for
    # the bootstrap.  This is what tenant config should refine later.
    days_per_period = 30.0
    samples = np.empty(n_iter, dtype=float)
    for i in range(n_iter):
        L = rng.choice(l_arr)
        n_periods = max(1, int(round(L / days_per_period)))
        samples[i] = rng.choice(d_arr, size=n_periods).sum()

    rop = float(np.quantile(samples, beta))
    mean_ltd = float(samples.mean())
    ss = max(0.0, rop - mean_ltd)
    return ss, rop


# ── EOQ ───────────────────────────────────────────────────────────────────────

def _wilson_eoq(annual_demand: float, order_cost: float, unit_holding_cost: float) -> float:
    if annual_demand <= 0 or order_cost <= 0 or unit_holding_cost <= 0:
        return 0.0
    return math.sqrt(2.0 * annual_demand * order_cost / unit_holding_cost)


def compute_eoq(
    *, annual_demand: float, unit_cost: float, order_cost: float,
    holding_cost_pct: float, price_breaks: Sequence[tuple[float, float]] = (),
) -> float:
    """
    Returns the order quantity that minimises total annual cost.  If
    price_breaks are supplied, evaluate TC at the Wilson optimum for each
    break and pick the lowest TC.
    """
    if not price_breaks:
        return _wilson_eoq(annual_demand, order_cost, unit_cost * holding_cost_pct)

    candidates: list[tuple[float, float]] = []  # (tc, q)
    for min_qty, cost_at_break in price_breaks:
        h = cost_at_break * holding_cost_pct
        q_star = _wilson_eoq(annual_demand, order_cost, h)
        if q_star < min_qty:
            q_star = min_qty
        tc = (annual_demand / q_star) * order_cost + (q_star / 2.0) * h + annual_demand * cost_at_break
        candidates.append((tc, q_star))
    candidates.sort(key=lambda t: t[0])
    return candidates[0][1]


# ── Public entry point ───────────────────────────────────────────────────────

def compute_recommendation(inp: OptimisationInput) -> OptimisationResult:
    """
    Compute (ROP, SS, EOQ) from a feature vector.  This function does NOT
    decide whether to emit a Recommendation entity — that's the generator's
    job (uses delta_threshold_pct from settings).
    """
    beta = beta_for(inp.criticality)

    mu_d, sigma_d = _mean_std(inp.demand_history)
    mu_l, sigma_l = _mean_std(inp.lead_time_days)
    notes: list[str] = []

    # Normality gate (DLD §4.3): try the normal model first; fall back to
    # bootstrap if Shapiro-Wilk rejects normality at α=0.05.
    method: Literal["normal", "bootstrap"] = "normal"
    if _SCIPY_OK and len(inp.demand_history) >= 8 and sigma_d > 0:
        _, p_value = stats.shapiro(np.asarray(inp.demand_history, dtype=float))
        if p_value < 0.05:
            method = "bootstrap"
            notes.append(f"Shapiro-Wilk p={p_value:.3g} < 0.05 → bootstrap quantile")

    if method == "normal":
        ss, rop = _normal_ss_rop(
            beta=beta, mu_d=mu_d, sigma_d=sigma_d, mu_l=mu_l / 30.0,
            sigma_l=sigma_l / 30.0,
        )
        # Convert ROP back to units of demand-per-period × periods_of_lead.
    else:
        ss, rop = _bootstrap_ss_rop(
            beta=beta, demand=inp.demand_history, lead=inp.lead_time_days,
        )

    annual_demand = sum(inp.demand_history[-12:]) if inp.demand_history else 0.0
    eoq = compute_eoq(
        annual_demand=annual_demand,
        unit_cost=inp.unit_cost,
        order_cost=inp.order_cost,
        holding_cost_pct=inp.holding_cost_pct,
        price_breaks=inp.price_breaks,
    )

    return OptimisationResult(
        item_id=inp.item_id, warehouse_id=inp.warehouse_id,
        rop=max(0, int(math.ceil(rop))),
        ss=max(0, int(math.ceil(ss))),
        eoq=max(0, int(math.ceil(eoq))),
        beta=beta,
        mean_demand_per_period=mu_d, std_demand_per_period=sigma_d,
        mean_lead_time_days=mu_l, std_lead_time_days=sigma_l,
        ss_method=method,
        notes=notes,
    )
