"""
Forecasts router — /v1/forecasts

GET  /v1/forecasts/{item_id}/{warehouse_id}   demand history + forecast series
POST /v1/forecasts:refresh                    on-demand re-forecast (Q1.2)

Resolution order on GET:
  1. Persisted forecast row (forecasts table) if recent enough.
  2. Live re-forecast — fetch MATUSETRANS, run the Q1.2 forecasting service,
     persist to forecasts table, return the result.
  3. Hardcoded seed fixture (only used when Maximo is unreachable AND the
     DB has no row — keeps the demo working without any data).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user
from app.forecasts import store as fc_store
from app.forecasts.maximo_client import fetch_item_forecast
from app.forecasts.models import ForecastPoint, ForecastSeries, HistoryPoint

logger = logging.getLogger(__name__)
router = APIRouter()

UserDep     = Annotated[CurrentUser, Depends(get_current_user)]
SettingsDep = Annotated[Settings,    Depends(get_settings)]

# ── Helpers ──────────────────────────────────────────────────────────────────

_REFRESH_AFTER = timedelta(hours=24)  # serve from DB cache if fresher than this


def _ensure_utc(dt: datetime) -> datetime:
    """SQLite strips tzinfo on roundtrip; add it back so comparisons work."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _load_from_db(item_id: str, warehouse_id: str) -> Optional[ForecastSeries]:
    from app import db
    if not db.is_enabled():
        return None
    try:
        from sqlalchemy import select, desc
        from app.models_db import ItemForecast
        async with db.session_scope() as s:
            stmt = (
                select(ItemForecast)
                .where(ItemForecast.item_id == item_id,
                       ItemForecast.warehouse_id == warehouse_id)
                .order_by(desc(ItemForecast.as_of))
                .limit(1)
            )
            row = (await s.execute(stmt)).scalars().first()
            if row is None:
                return None
            return ForecastSeries(
                item_id=row.item_id,
                warehouse_id=row.warehouse_id,
                history=[HistoryPoint(**p) for p in row.history_json],
                forecast=[ForecastPoint(**p) for p in row.forecast_json],
                recommended_reorder_point=0.0,
                recommended_safety_stock=0.0,
                model_version=row.model_version,
                as_of=row.as_of.isoformat().replace("+00:00", "Z"),
            ), _ensure_utc(row.as_of)
    except Exception as exc:
        logger.warning("Forecast DB load failed for %s/%s: %s", item_id, warehouse_id, exc)
        return None


async def _persist(item_id: str, warehouse_id: str, series: ForecastSeries,
                   pattern: str, adi: float, cv2: float) -> None:
    from app import db
    if not db.is_enabled():
        return
    try:
        from app.models_db import ItemForecast
        async with db.session_scope() as s:
            s.add(ItemForecast(
                item_id=item_id,
                warehouse_id=warehouse_id,
                model_version=series.model_version,
                demand_pattern=pattern,
                adi=adi,
                cv_squared=cv2,
                history_json=[p.model_dump(by_alias=False) for p in series.history],
                forecast_json=[p.model_dump(by_alias=False) for p in series.forecast],
                as_of=datetime.now(timezone.utc),
            ))
    except Exception as exc:
        logger.warning("Forecast persist failed for %s/%s: %s", item_id, warehouse_id, exc)


async def _live_refresh(item_id: str, warehouse_id: str, settings: Settings,
                        *, horizon: int = 12) -> Optional[ForecastSeries]:
    """
    Pull demand history, run the Q1.2 forecasting service, persist, return.
    """
    # Re-use the existing forecasts.maximo_client which already aggregates
    # MATUSETRANS into a 24-month vector for this item.
    raw = await fetch_item_forecast(settings, item_id, warehouse_id)
    if raw is None or not raw.history:
        return None
    history_vec = [hp.qty for hp in raw.history]

    try:
        from app.forecasting.service import forecast as run_forecast
        res = run_forecast(item_id=item_id, warehouse_id=warehouse_id,
                           history=history_vec, horizon=horizon)
    except Exception as exc:
        logger.warning("Forecasting service failed for %s/%s: %s", item_id, warehouse_id, exc)
        return None

    # Build forecast points (months follow the same scheme as the existing
    # seed: next month forward).
    months = _next_months(len(res.points))
    fc_points = [
        ForecastPoint(month=months[i], mean=p.mean, p10=p.p10, p90=p.p90)
        for i, p in enumerate(res.points)
    ]

    series = ForecastSeries(
        item_id=item_id,
        warehouse_id=warehouse_id,
        history=raw.history,
        forecast=fc_points,
        recommended_reorder_point=raw.recommended_reorder_point,
        recommended_safety_stock=raw.recommended_safety_stock,
        model_version=res.model_version,
        as_of=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    await _persist(item_id, warehouse_id, series,
                   pattern=res.classification.pattern,
                   adi=res.classification.adi,
                   cv2=res.classification.cv_squared)
    return series


def _next_months(n: int) -> list[str]:
    today = datetime.now(timezone.utc).date().replace(day=1)
    out: list[str] = []
    cur = today
    for _ in range(n):
        # advance by ~30 days then re-anchor to month start
        next_month = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append(next_month.strftime("%Y-%m"))
        cur = next_month
    return out


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/{item_id}/{warehouse_id}",
    response_model=ForecastSeries,
    response_model_by_alias=True,
    summary="Get demand history and forecast for an item × warehouse",
)
async def get_forecast(
    item_id:      str,
    warehouse_id: str,
    settings:     SettingsDep,
    _user:        UserDep,
    fresh:        Annotated[bool, Query(description="Bypass DB cache and re-forecast")] = False,
) -> ForecastSeries:
    # 1. DB cache hit (recent enough)
    if not fresh:
        cached = await _load_from_db(item_id, warehouse_id)
        if cached is not None:
            series, as_of = cached
            if datetime.now(timezone.utc) - as_of < _REFRESH_AFTER:
                return series

    # 2. Live re-forecast via the Q1.2 forecasting service
    live = await _live_refresh(item_id, warehouse_id, settings)
    if live is not None:
        return live

    # 3. Hardcoded seed — only as a last resort
    seed = fc_store.get_forecast(item_id, warehouse_id)
    if seed is not None:
        return seed

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"No forecast data found for item '{item_id}' "
            f"in warehouse '{warehouse_id}'"
        ),
    )


@router.post(":refresh", summary="Re-forecast on demand (Q1.2)")
async def refresh_forecasts(
    settings: SettingsDep,
    _user:    UserDep,
    items: Annotated[Optional[str], Query(description="CSV of itemnums; default all from current inventory pull")] = None,
    history_months: Annotated[int, Query(ge=3, le=60)] = 24,
) -> dict:
    """
    Refreshes the forecasts table for the given items (or all current
    inventory items if `items` is omitted) by running the same orchestrator
    that the nightly batch uses.

    The forecasts subset of the orchestrator's output is what this endpoint
    advertises; the recommendations subset is also updated as a side effect
    because the orchestrator persists everything atomically.
    """
    from app.orchestration.nightly import run_batch
    item_filter = (
        {x.strip() for x in items.split(",") if x.strip()} if items else None
    )
    res = await run_batch(
        item_filter=item_filter, history_months=history_months, run_backtest=True,
    )
    return {
        "itemsWithDemand":    res.items_with_demand,
        "itemsWithLeadTime":  res.items_with_leadtime,
        "recommendations":    res.recommendations,
        "backtestRows":       res.backtest_rows,
        "elapsedSeconds":     round(res.elapsed_seconds, 2),
    }
