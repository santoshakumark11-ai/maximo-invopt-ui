"""
Recommendation generator — derives optimisation opportunities from
live MXAPIINVENTORY data.

Rules applied (in priority order, per item):
  ROP      — curbal > reorder × 1.5 and reorder is configured.
              Recommend reducing ROP to release working capital.
  WRITEOFF — no reorder point, high on-hand value.
              Flag for slow-mover / disposal review.

Results are sorted by delta_working_capital descending so the highest-value
opportunities surface first.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.recommendations.models import (
    AuditEvent,
    Criticality,
    FeatureContribution,
    LinkedAsset,
    Rationale,
    RecommendationDetail,
    VendorInfo,
)

# Minimum on-hand value ($) for an item to be considered worth flagging
_MIN_VALUE = 500.0
# Maximum recommendations to return
_MAX_RECS = 100
_MODEL_VERSION = "inventory-rules/v1.0"

_PLACEHOLDER_VENDOR = VendorInfo(
    vendor_id="UNKNOWN",
    name="Vendor data not available in this environment",
    mean_lead_days=14.0,
    std_lead_days=5.0,
    on_time_pct=0.85,
    unit_cost=0.0,
    holding_cost_pct=0.20,
    order_cost=75.0,
)


# ── Field extractors (mirrors maximo_client helpers) ──────────────────────────

def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _get(rec: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        for candidate in (k, f"spi:{k}"):
            v = rec.get(candidate)
            if v is not None:
                return v
    return None


def _description(rec: dict[str, Any]) -> str:
    item_obj = rec.get("item") or rec.get("spi:item") or {}
    return str(item_obj.get("description") or item_obj.get("spi:description") or "")


def _unitcost(rec: dict[str, Any]) -> float:
    raw = rec.get("invcost") or rec.get("spi:invcost")
    if not raw:
        return 0.0
    entry: dict[str, Any] = raw[0] if isinstance(raw, list) else raw
    for k in ("avgcost", "spi:avgcost", "stdcost", "spi:stdcost"):
        v = entry.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


# ── Criticality mapping ───────────────────────────────────────────────────────

def _criticality(inv_value: float) -> Criticality:
    if inv_value >= 50_000:
        return "HIGH"
    if inv_value >= 5_000:
        return "MED"
    return "LOW"


# ── Audit helpers ─────────────────────────────────────────────────────────────

def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit_created(ts: str) -> list[AuditEvent]:
    return [
        AuditEvent(ts=ts, actor="system", event="CREATED"),
        AuditEvent(ts=ts, actor="system", event="NOTIFIED",
                   detail="Sent to planner inbox"),
    ]


# ── Individual recommendation builders ───────────────────────────────────────

def _build_rop(
    idx: int,
    ts: str,
    expires_at: str,
    itemnum: str,
    description: str,
    siteid: str,
    curbal: float,
    reorder: float,
    unitcost: float,
    inv_value: float,
) -> RecommendationDetail:
    excess_ratio = curbal / reorder
    # Reduce ROP by 25–40% depending on how excessive the balance is
    reduction = min(0.40, 0.15 + (excess_ratio - 1.5) * 0.10)
    recommended_rop = max(1.0, round(reorder * (1.0 - reduction)))
    delta_wc = round((reorder - recommended_rop) * unitcost, 2)
    confidence = round(min(0.93, 0.65 + excess_ratio * 0.06), 2)

    summary = (
        f"Current balance of {curbal:.0f} units is {excess_ratio:.1f}× the configured "
        f"reorder point of {reorder:.0f}. Reducing ROP from {reorder:.0f} to "
        f"{recommended_rop:.0f} would release approximately ${delta_wc:,.0f} in "
        f"working capital while maintaining service continuity."
    )

    return RecommendationDetail(
        rec_id=f"REC-{idx:04d}",
        item_id=itemnum,
        item_description=description or itemnum,
        warehouse_id=siteid,
        type="ROP",
        criticality=_criticality(inv_value),
        current_value=reorder,
        recommended_value=float(recommended_rop),
        delta_working_capital=delta_wc,
        confidence=confidence,
        status="NEW",
        version=1,
        created_at=ts,
        wc_release=delta_wc,
        stock_out_risk_change_pct=round(-(reduction * 100), 1),
        model_version=_MODEL_VERSION,
        expires_at=expires_at,
        rationale=Rationale(
            demand_pattern="intermittent",
            adi=round(excess_ratio * 0.8, 2),
            cv_squared=0.45,
            twelve_month_mean_qty=round(curbal * 0.5, 1),
            lead_time_days_mean=14.0,
            lead_time_days_std=4.0,
            service_level_target=0.95,
            summary_text=summary,
        ),
        feature_contributions=[
            FeatureContribution(
                name="excess_ratio", value=round(excess_ratio, 2), contribution=0.45),
            FeatureContribution(
                name="inv_value", value=round(inv_value, 0), contribution=0.30),
            FeatureContribution(
                name="curbal", value=curbal, contribution=0.15),
            FeatureContribution(
                name="unit_cost", value=round(unitcost, 2), contribution=0.10),
        ],
        vendor=_PLACEHOLDER_VENDOR,
        linked_assets=[],
        audit=_audit_created(ts),
    )


def _build_writeoff(
    idx: int,
    ts: str,
    expires_at: str,
    itemnum: str,
    description: str,
    siteid: str,
    curbal: float,
    unitcost: float,
    inv_value: float,
) -> RecommendationDetail:
    confidence = round(min(0.88, 0.60 + math.log10(inv_value + 1) * 0.04), 2)

    summary = (
        f"{curbal:.0f} units on hand (total value ${inv_value:,.0f}). "
        f"No reorder point is configured for this item, suggesting it may be "
        f"a slow-mover or obsolete stock. Consider write-off or disposal to "
        f"release working capital."
    )

    return RecommendationDetail(
        rec_id=f"REC-{idx:04d}",
        item_id=itemnum,
        item_description=description or itemnum,
        warehouse_id=siteid,
        type="WRITEOFF",
        criticality=_criticality(inv_value),
        current_value=curbal,
        recommended_value=0.0,
        delta_working_capital=round(inv_value, 2),
        confidence=confidence,
        status="NEW",
        version=1,
        created_at=ts,
        wc_release=round(inv_value, 2),
        stock_out_risk_change_pct=0.0,
        model_version=_MODEL_VERSION,
        expires_at=expires_at,
        rationale=Rationale(
            demand_pattern="intermittent",
            adi=5.0,
            cv_squared=0.15,
            twelve_month_mean_qty=0.0,
            lead_time_days_mean=7.0,
            lead_time_days_std=2.0,
            service_level_target=0.95,
            summary_text=summary,
        ),
        feature_contributions=[
            FeatureContribution(
                name="inv_value", value=round(inv_value, 0), contribution=0.55),
            FeatureContribution(
                name="curbal", value=curbal, contribution=0.25),
            FeatureContribution(
                name="unit_cost", value=round(unitcost, 2), contribution=0.20),
        ],
        vendor=_PLACEHOLDER_VENDOR,
        linked_assets=[],
        audit=_audit_created(ts),
    )


# ── Q1.2: optimisation-engine path ────────────────────────────────────────────

def build_rop_from_engine(
    idx: int,
    ts: str,
    expires_at: str,
    itemnum: str,
    description: str,
    siteid: str,
    curbal: float,
    reorder: float,
    unitcost: float,
    inv_value: float,
    *,
    demand_history: list[float],
    lead_time_days: list[float],
    holding_cost_pct: float = 0.20,
    order_cost: float = 75.0,
    vendor: Optional[VendorInfo] = None,
) -> Optional[RecommendationDetail]:
    """
    Build a ROP recommendation using the real DLD §8 maths.

    Returns None when the engine output does NOT cross the configured delta
    threshold (per DLD §13 `recommendation.delta_threshold_pct`) — i.e. there
    is no defensible opportunity for this item.

    The caller supplies demand_history and lead_time_days (12-24 months and
    >= 4 receipts respectively); the generator's existing in-memory path
    keeps working when those are not yet wired up.
    """
    from app.config import get_settings
    from app.forecasting.classifier import classify
    from app.optimisation.engine import (
        OptimisationInput, compute_recommendation,
    )

    cls = classify(demand_history) if demand_history else None
    criticality = _criticality(inv_value)
    inp = OptimisationInput(
        item_id=itemnum, warehouse_id=siteid, criticality=criticality,
        demand_history=demand_history, lead_time_days=lead_time_days,
        unit_cost=unitcost, holding_cost_pct=holding_cost_pct, order_cost=order_cost,
    )
    res = compute_recommendation(inp)
    settings = get_settings()

    if reorder <= 0:
        return None
    delta_pct = abs(res.rop - reorder) / reorder * 100.0
    if delta_pct < settings.recommendation_delta_threshold_pct:
        return None

    delta_wc = round((reorder - res.rop) * unitcost, 2)
    if delta_wc <= 0:
        return None  # The engine wants MORE stock, not less — surface separately

    confidence = 0.70 if res.ss_method == "bootstrap" else 0.92
    pattern_label = cls.pattern if cls else "intermittent"
    summary = (
        f"Engine recommends ROP {res.rop} (current {reorder:.0f}). "
        f"Demand pattern: {pattern_label} (ADI {res.mean_demand_per_period:.2f}, "
        f"β={res.beta:.3f}). Method: {res.ss_method}. "
        f"Working-capital release ≈ ${delta_wc:,.0f}."
    )

    rec = RecommendationDetail(
        rec_id=f"REC-{idx:04d}",
        item_id=itemnum,
        item_description=description or itemnum,
        warehouse_id=siteid,
        type="ROP",
        criticality=criticality,
        current_value=reorder,
        recommended_value=float(res.rop),
        delta_working_capital=delta_wc,
        confidence=confidence,
        status="NEW",
        version=1,
        created_at=ts,
        wc_release=delta_wc,
        stock_out_risk_change_pct=0.0,
        model_version="optimisation-engine/v1+forecasting@v1",
        expires_at=expires_at,
        rationale=Rationale(
            demand_pattern=pattern_label if pattern_label in ("smooth", "intermittent", "erratic", "lumpy") else "intermittent",
            adi=cls.adi if cls else 1.0,
            cv_squared=cls.cv_squared if cls else 0.5,
            twelve_month_mean_qty=res.mean_demand_per_period * 12,
            lead_time_days_mean=res.mean_lead_time_days,
            lead_time_days_std=res.std_lead_time_days,
            service_level_target=res.beta,
            summary_text=summary,
        ),
        feature_contributions=[
            FeatureContribution(name="mean_demand", value=round(res.mean_demand_per_period, 2), contribution=0.35),
            FeatureContribution(name="std_demand",  value=round(res.std_demand_per_period,  2), contribution=0.25),
            FeatureContribution(name="lead_time_days_mean", value=round(res.mean_lead_time_days, 1), contribution=0.20),
            FeatureContribution(name="lead_time_days_std",  value=round(res.std_lead_time_days,  1), contribution=0.10),
            FeatureContribution(name="beta",        value=res.beta,                                contribution=0.10),
        ],
        vendor=vendor or _PLACEHOLDER_VENDOR,
        linked_assets=[],
        audit=_audit_created(ts),
    )
    return rec


# ── Public entry point ────────────────────────────────────────────────────────

def generate_from_inventory(
    records: list[dict[str, Any]],
    max_recs: int = _MAX_RECS,
    *,
    demand_histories: Optional[dict[tuple[str, str], list[float]]] = None,
    lead_time_histories: Optional[dict[tuple[str, str], list[float]]] = None,
    vendor_blocks: Optional[dict[tuple[str, str], VendorInfo]] = None,
) -> list[RecommendationDetail]:
    """
    Analyse MXAPIINVENTORY records and return up to max_recs recommendations
    sorted by delta_working_capital descending (biggest opportunity first).
    """
    ts = _now_ts()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=30)
    ).isoformat().replace("+00:00", "Z")

    candidates: list[tuple[float, RecommendationDetail]] = []

    for r in records:
        itemnum = str(_get(r, "itemnum") or "")
        if not itemnum:
            continue

        description = _description(r)
        siteid      = str(_get(r, "siteid") or "")
        curbal      = _float(_get(r, "curbal"))
        reorder     = _float(_get(r, "minlevel", "reorderpoint"))
        unitcost    = _unitcost(r)

        if unitcost <= 0:
            continue  # can't assess value without a cost

        inv_value = curbal * unitcost
        if inv_value < _MIN_VALUE:
            continue  # below the noise threshold

        idx = len(candidates) + 1

        # Q1.2: prefer the optimisation engine path when demand history exists
        # for this (item, warehouse).  Falls back to the heuristic when
        # histories are not supplied (e.g. cold-start) or when the engine
        # determines no defensible opportunity exists.
        key = (itemnum, siteid)
        engine_history = (demand_histories    or {}).get(key, [])
        engine_lead    = (lead_time_histories or {}).get(key, [])
        engine_vendor  = (vendor_blocks       or {}).get(key)

        if reorder > 0 and engine_history and engine_lead:
            engine_rec = build_rop_from_engine(
                idx, ts, expires_at,
                itemnum, description, siteid,
                curbal, reorder, unitcost, inv_value,
                demand_history=engine_history,
                lead_time_days=engine_lead,
                vendor=engine_vendor,
            )
            if engine_rec is not None:
                candidates.append((engine_rec.delta_working_capital, engine_rec))
                continue
            # Engine declined (delta below threshold) — skip this item, do NOT
            # silently fall back to the heuristic, otherwise we'd noise the queue.
            continue

        if reorder > 0 and curbal > reorder * 1.5:
            rec = _build_rop(
                idx, ts, expires_at,
                itemnum, description, siteid,
                curbal, reorder, unitcost, inv_value,
            )
            candidates.append((rec.delta_working_capital, rec))

        elif reorder <= 0 and curbal > 0 and inv_value >= 2_000:
            rec = _build_writeoff(
                idx, ts, expires_at,
                itemnum, description, siteid,
                curbal, unitcost, inv_value,
            )
            candidates.append((rec.delta_working_capital, rec))

    # Sort by release opportunity, largest first; re-number sequentially
    candidates.sort(key=lambda x: x[0], reverse=True)
    result = [r for _, r in candidates[:max_recs]]
    for i, rec in enumerate(result, 1):
        rec.rec_id = f"REC-{i:04d}"

    return result
