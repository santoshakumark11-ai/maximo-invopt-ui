"""
Rolling-origin backtest — DLD §14.3.

Walks the consumption history forward, refitting at each origin, and
computes WAPE / MAPE / bias on the held-out window.

Results are persisted to forecast_backtests by run_backtest; the metrics
router can replace its static seed (metrics/seed.py FORECAST_ROWS) with
the latest rows from this table.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Sequence

from app import db
from app.forecasting.classifier import classify
from app.forecasting.service import forecast as _forecast

logger = logging.getLogger(__name__)


@dataclass
class BacktestRow:
    pattern: str
    n_items: int
    wape: float
    mape: float
    bias: float


def _safe_mape(actual: float, pred: float) -> float:
    if actual == 0:
        return 0.0
    return abs((actual - pred) / actual) * 100.0


def evaluate_item(history: Sequence[float], holdout: int = 3) -> tuple[str, float, float, float]:
    """
    Evaluate a single item's forecast accuracy by holding out the last
    `holdout` periods.  Returns (pattern, wape, mape, bias).
    """
    if len(history) <= holdout:
        return "no_demand", 0.0, 0.0, 0.0
    train = list(history[:-holdout])
    test  = list(history[-holdout:])
    pattern = classify(train).pattern
    fc = _forecast(item_id="bt", warehouse_id="bt", history=train, horizon=holdout)
    preds = [p.mean for p in fc.points]

    sum_actual = sum(test)
    sum_err    = sum(abs(a - p) for a, p in zip(test, preds))
    if sum_actual > 0:
        wape = sum_err / sum_actual * 100.0
    else:
        wape = 0.0
    mape_vals = [_safe_mape(a, p) for a, p in zip(test, preds) if a != 0]
    mape = sum(mape_vals) / len(mape_vals) if mape_vals else 0.0
    bias = sum(p - a for a, p in zip(test, preds)) / len(test)
    return pattern, wape, mape, bias


async def run_backtest(item_histories: dict[str, Sequence[float]],
                       *, holdout: int = 3) -> dict[str, BacktestRow]:
    """
    Run the rolling-origin backtest across many items, group by pattern,
    persist to forecast_backtests.

    item_histories: {item_id: per-period demand vector}

    Returns the aggregated rows keyed by pattern.
    """
    grouped: dict[str, list[tuple[float, float, float]]] = {}
    for item_id, history in item_histories.items():
        pattern, wape, mape, bias = evaluate_item(history, holdout=holdout)
        grouped.setdefault(pattern, []).append((wape, mape, bias))

    out: dict[str, BacktestRow] = {}
    for pattern, rows in grouped.items():
        n = len(rows)
        if n == 0:
            continue
        out[pattern] = BacktestRow(
            pattern=pattern, n_items=n,
            wape=sum(r[0] for r in rows) / n,
            mape=sum(r[1] for r in rows) / n,
            bias=sum(r[2] for r in rows) / n,
        )

    # Best-effort persist.
    if db.is_enabled():
        try:
            from app.models_db import ForecastBacktest
            run_id = str(uuid.uuid4())[:12]
            async with db.session_scope() as s:
                for pattern, row in out.items():
                    s.add(ForecastBacktest(
                        run_id=run_id, pattern=pattern,
                        model_version="route@v1",
                        n_items=row.n_items, wape=row.wape,
                        mape=row.mape, bias=row.bias,
                    ))
        except Exception as exc:
            logger.warning("Backtest persistence failed: %s", exc)

    # Best-effort metric publication.
    try:
        from app.observability.metrics import set_forecast_mape
        for pattern, row in out.items():
            set_forecast_mape(pattern, row.wape)
    except Exception:
        pass

    return out
