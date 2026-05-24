"""
Metrics router — five endpoints under /v1/metrics

GET /v1/metrics/kpi-summary          — aggregate KPI counts & total value
GET /v1/metrics/inventory-by-status  — count/value split by health bucket
GET /v1/metrics/top-items-by-risk    — ranked list of below-reorder items
GET /v1/metrics/forecast-accuracy    — per-item MAPE/MAE/bias (seed data)
GET /v1/metrics/recommendations      — prioritised action list (seed data)

All endpoints require a valid Bearer JWT (get_current_user dependency).
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user
from app.metrics.maximo_client import (
    fetch_inventory,
    compute_kpi_summary,
    compute_inventory_by_status,
    compute_top_items_by_risk,
)
from app.metrics.models import (
    KpiSummary,
    InventoryByStatus,
    StatusBucket,
    TopItemsByRisk,
    TopItem,
    ForecastAccuracy,
    ForecastAccuracyRow,
    Recommendation,
)
from app.metrics.seed import FORECAST_ROWS, OVERALL_MAPE, RECOMMENDATIONS

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Convenience type aliases ──────────────────────────────────────────────────
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]


# ── 1. KPI Summary ────────────────────────────────────────────────────────────

@router.get(
    "/kpi-summary",
    response_model=KpiSummary,
    summary="Aggregate KPI counts and total inventory value",
)
async def kpi_summary(settings: SettingsDep, _user: UserDep) -> KpiSummary:
    records = await fetch_inventory(settings)
    if not records:
        logger.warning("No inventory records returned from Maximo — returning zeros")
    data = compute_kpi_summary(records)
    return KpiSummary(**data)


# ── 2. Inventory By Status ────────────────────────────────────────────────────

@router.get(
    "/inventory-by-status",
    response_model=InventoryByStatus,
    summary="Item count and value split by inventory health status",
)
async def inventory_by_status(settings: SettingsDep, _user: UserDep) -> InventoryByStatus:
    records = await fetch_inventory(settings)
    buckets_data = compute_inventory_by_status(records)
    return InventoryByStatus(
        buckets=[StatusBucket(**b) for b in buckets_data]
    )


# ── 3. Top Items By Reorder Risk ──────────────────────────────────────────────

@router.get(
    "/top-items-by-risk",
    response_model=TopItemsByRisk,
    summary="Top items most at risk of stockout, ranked by risk score",
)
async def top_items_by_risk(
    settings: SettingsDep,
    _user: UserDep,
    limit: int = 20,
) -> TopItemsByRisk:
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 100",
        )
    records = await fetch_inventory(settings)
    items_data = compute_top_items_by_risk(records, limit=limit)
    return TopItemsByRisk(
        items=[TopItem(**i) for i in items_data]
    )


# ── 4. Forecast Accuracy ──────────────────────────────────────────────────────

@router.get(
    "/forecast-accuracy",
    response_model=ForecastAccuracy,
    summary="Per-item forecast accuracy (MAPE, MAE, bias)",
)
def forecast_accuracy(_user: UserDep) -> ForecastAccuracy:
    """
    Returns seed forecast accuracy data.
    Phase 2 will replace this with real forecast engine output.
    """
    return ForecastAccuracy(
        rows=FORECAST_ROWS,
        overall_mape=OVERALL_MAPE,
    )


# ── 5. Recommendations ────────────────────────────────────────────────────────

@router.get(
    "/recommendations",
    response_model=list[Recommendation],
    summary="Prioritised inventory optimisation recommendations",
)
def recommendations(_user: UserDep) -> list[Recommendation]:
    """
    Returns seed recommendations.
    Phase 2 will replace this with real optimisation engine output.
    """
    return RECOMMENDATIONS
