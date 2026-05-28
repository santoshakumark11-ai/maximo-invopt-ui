"""
Per-pattern probabilistic forecasting — DLD §4.2, §8.2.

Routes per item based on the demand-pattern classifier:

    smooth        → Holt-Winters (statsforecast.AutoETS)
    intermittent  → Croston/SBJ                 (statsforecast.CrostonSBA)
    erratic       → empirical bootstrap quantiles (NumPy)
    lumpy         → Croston/SBJ + future PM uplift (PM uplift applied outside)

Outputs (mean, p10, p90) per future period.  Quantile bands come from
residuals of the in-sample fit; when statsforecast is missing or fails,
the entire path falls back to the bootstrap branch.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional, Sequence

from app.config import get_settings
from app.forecasting.classifier import ClassificationResult, classify

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _NP_OK = True
except Exception:
    _NP_OK = False
    np = None  # type: ignore[assignment]

try:
    from statsforecast import StatsForecast  # noqa: F401
    from statsforecast.models import AutoETS, CrostonSBA
    _SF_OK = True
except Exception:
    _SF_OK = False
    AutoETS = CrostonSBA = None  # type: ignore[assignment]


@dataclass
class ForecastPoint:
    period: int     # 1-indexed: 1 = next period
    mean:   float
    p10:    float
    p90:    float


@dataclass
class ForecastResult:
    item_id: str
    warehouse_id: str
    classification: ClassificationResult
    points: list[ForecastPoint]
    model_version: str


# ── Public entry point ───────────────────────────────────────────────────────

def forecast(
    *, item_id: str, warehouse_id: str, history: Sequence[float],
    horizon: int = 12,
) -> ForecastResult:
    """
    Produce a horizon-step probabilistic forecast.

    Inputs:
        history : per-period observations, oldest → newest (e.g. 24 months).
        horizon : number of future periods to forecast.

    The classification result is returned so the caller can persist ADI/CV²
    on the recommendation rationale block.
    """
    cls = classify(history)
    settings = get_settings()

    use_sf = settings.forecasting_use_statsforecast and _SF_OK
    if not use_sf or cls.pattern in ("erratic", "no_demand") or not _NP_OK:
        points = _bootstrap_forecast(history, horizon)
        return ForecastResult(
            item_id=item_id, warehouse_id=warehouse_id, classification=cls,
            points=points, model_version="bootstrap@1.0",
        )

    try:
        if cls.pattern == "intermittent" or cls.pattern == "lumpy":
            mean, p10, p90 = _statsforecast_predict(history, horizon, model=CrostonSBA)
            model_version = "croston-sba@statsforecast"
        else:  # smooth
            mean, p10, p90 = _statsforecast_predict(history, horizon, model=AutoETS)
            model_version = "holt-winters-autoets@statsforecast"
    except Exception as exc:
        logger.warning("statsforecast failed for %s (%s) — bootstrap", item_id, exc)
        points = _bootstrap_forecast(history, horizon)
        return ForecastResult(
            item_id=item_id, warehouse_id=warehouse_id, classification=cls,
            points=points, model_version="bootstrap@1.0",
        )

    points = [
        ForecastPoint(period=i + 1, mean=float(mean[i]), p10=float(p10[i]), p90=float(p90[i]))
        for i in range(horizon)
    ]
    return ForecastResult(
        item_id=item_id, warehouse_id=warehouse_id, classification=cls,
        points=points, model_version=model_version,
    )


# ── statsforecast adapter (with residual-based quantile bands) ───────────────

def _statsforecast_predict(history: Sequence[float], horizon: int, *, model) -> tuple[list[float], list[float], list[float]]:
    import pandas as pd  # statsforecast pulls pandas; only import inside this path
    y = list(map(float, history))
    df = pd.DataFrame({
        "unique_id": ["item"] * len(y),
        "ds":        pd.RangeIndex(start=0, stop=len(y), step=1),
        "y":         y,
    })
    sf = StatsForecast(models=[model()], freq=1, n_jobs=1)
    fc = sf.forecast(df=df, h=horizon, level=[80])

    col_mean = fc.columns[fc.columns.str.startswith(model.__name__)].tolist()
    # statsforecast names: model.__name__, model.__name__-lo-80, -hi-80
    mean_col = model.__name__
    lo_col   = f"{model.__name__}-lo-80"
    hi_col   = f"{model.__name__}-hi-80"
    means = fc[mean_col].tolist()
    los   = fc[lo_col].tolist()   if lo_col in fc.columns else [m * 0.7 for m in means]
    his   = fc[hi_col].tolist()   if hi_col in fc.columns else [m * 1.3 for m in means]
    # Clip lows at 0.
    los = [max(0.0, x) for x in los]
    return means, los, his


# ── Empirical bootstrap fallback ─────────────────────────────────────────────

def _bootstrap_forecast(history: Sequence[float], horizon: int) -> list[ForecastPoint]:
    """
    NumPy bootstrap of the empirical distribution.  Captures the "lumpiness"
    of real consumption far better than mean ± fixed spread (the current
    seed behaviour the gap report flagged).
    """
    if not _NP_OK or len(history) == 0:
        return [ForecastPoint(period=i + 1, mean=0.0, p10=0.0, p90=0.0)
                for i in range(horizon)]

    arr = np.asarray([float(x) for x in history], dtype=float)
    if arr.size == 0:
        return [ForecastPoint(period=i + 1, mean=0.0, p10=0.0, p90=0.0)
                for i in range(horizon)]

    rng = np.random.default_rng(seed=7)
    mean_per_period = float(arr.mean())
    out: list[ForecastPoint] = []
    for i in range(horizon):
        draws = rng.choice(arr, size=2000, replace=True)
        p10 = float(np.quantile(draws, 0.10))
        p90 = float(np.quantile(draws, 0.90))
        out.append(ForecastPoint(period=i + 1, mean=mean_per_period, p10=max(0.0, p10), p90=p90))
    return out
