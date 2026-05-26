"""
Metrics router — /v1/metrics

Frontend-compatible compat endpoints (what React queries call):
  GET /dashboard                — DashboardKpis shape
  GET /working-capital-trend    — WorkingCapitalPoint[] shape
  GET /recommendations-by-status — StatusMixItem[] shape
  GET /forecast-accuracy        — ForecastAccuracyRow[] shape (array)
  GET /top-items                — TopItem[] shape (frontend)

Canonical backend endpoints:
  GET /kpi-summary              — aggregate KPI counts & total value
  GET /inventory-by-status      — count/value split by health bucket
  GET /top-items-by-risk        — ranked list of below-reorder items
  GET /recommendations          — prioritised action list (seed data)

All endpoints require a valid Bearer JWT.
"""
import logging
import math
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

SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]


# ─────────────────────────────────────────────────────────────────────────────
# COMPAT LAYER — shapes the React frontend expects
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard", summary="Dashboard KPIs (frontend-compatible)")
async def dashboard_kpis(settings: SettingsDep, _user: UserDep) -> dict:
    """
    Returns DashboardKpis shape:
      { inventoryValue, workingCapital, serviceLevel, openRecommendations }

    Derived from live MXINVENTORY data + recommendation store counts.
    """
    from app.recommendations import store as rec_store

    records = await fetch_inventory(settings)
    kpi = compute_kpi_summary(records)

    total_items = kpi["total_items"]
    healthy = total_items - kpi["below_reorder"] - kpi["stockout_risk"]
    service_level = round(healthy / total_items * 100, 1) if total_items > 0 else 0.0

    # Count open recommendations (NEW or PENDING)
    open_recs = sum(
        1 for r in rec_store.get_all()
        if r.status in ("NEW", "PENDING")
    )

    return {
        "inventoryValue":      round(kpi["total_value"], 2),
        "workingCapital":      round(kpi["total_value"] * 0.35, 2),  # ~35% of stock = working capital
        "serviceLevel":        service_level,
        "openRecommendations": open_recs,
    }


@router.get("/working-capital-trend", summary="12-month working capital trend (frontend-compatible)")
async def working_capital_trend(settings: SettingsDep, _user: UserDep) -> list[dict]:
    """
    Returns WorkingCapitalPoint[] shape: [{ period, value }, ...]

    Derives current working capital from live MXINVENTORY, then projects a
    12-month synthetic trend ending at the current value.  Replace with a
    real time-series query once Maximo MXINVTRANS history is integrated.
    """
    from datetime import date, timedelta

    records = await fetch_inventory(settings)
    kpi = compute_kpi_summary(records)
    current_wc = kpi["total_value"] * 0.35

    # Generate 12 monthly points ending at current month
    today = date.today()
    points = []
    # Simple sinusoidal trend: gentle upward drift + seasonal dip mid-year
    for i in range(11, -1, -1):
        month_date = (today.replace(day=1) - timedelta(days=i * 30))
        period = month_date.strftime("%Y-%m")
        # seasonal factor: slight dip in middle months
        seasonal = 1.0 - 0.04 * math.sin(math.pi * month_date.month / 12)
        # long-term growth factor (mild decline toward current)
        growth = 1.0 + 0.08 * (i / 11)
        value = round(current_wc * seasonal * growth, 2)
        points.append({"period": period, "value": value})

    return points


@router.get("/recommendations-by-status", summary="Recommendation counts by status (frontend-compatible)")
def recommendations_by_status(_user: UserDep) -> list[dict]:
    """
    Returns StatusMixItem[] shape: [{ status, count }, ...]

    Sourced from the in-memory recommendations store.
    """
    from app.recommendations import store as rec_store
    from collections import Counter

    counts: Counter = Counter(r.status for r in rec_store.get_all())
    # Include all known statuses even if count is 0
    all_statuses = ["NEW", "PENDING", "APPROVED", "APPLIED", "REJECTED"]
    return [{"status": s, "count": counts.get(s, 0)} for s in all_statuses]


@router.get("/forecast-accuracy", summary="Forecast accuracy rows (frontend-compatible)")
def forecast_accuracy_compat(_user: UserDep) -> list[dict]:
    """
    Returns ForecastAccuracyRow[] shape: [{ itemId, description, wape, bias }, ...]

    Maps seed data fields (item_num → itemId, mape → wape).
    """
    return [
        {
            "itemId":      row.item_num,
            "description": row.description,
            "wape":        row.mape,   # mape ≈ wape for this seed data
            "bias":        row.bias,
        }
        for row in FORECAST_ROWS
    ]


@router.get("/top-items", summary="Top items by release potential (frontend-compatible)")
async def top_items_compat(settings: SettingsDep, _user: UserDep) -> list[dict]:
    """
    Returns TopItem[] shape: [{ itemId, description, releaseValue, site, criticality }, ...]

    Derived from live MXINVENTORY top-items-by-risk, with criticality mapped
    from risk score (>= 70 → high, >= 40 → med, else low).
    """
    records = await fetch_inventory(settings)
    items_data = compute_top_items_by_risk(records, limit=10)

    result = []
    for item in items_data:
        risk        = item.get("risk_score", 0)
        curbal      = item.get("current_bal", 0)
        reorder     = item.get("reorder_point", 0)
        unit_cost   = item.get("unit_cost", 0)
        criticality = "high" if risk >= 70 else ("med" if risk >= 40 else "low")

        # Release value:
        #   - If reorder point set: excess above reorder × unit cost
        #   - Otherwise: full on-hand value (items ranked by total inv value)
        if reorder > 0:
            excess = max(0.0, curbal - reorder)
            release_value = round(excess * unit_cost, 2)
        else:
            release_value = round(curbal * unit_cost, 2)

        result.append({
            "itemId":       item.get("item_num", ""),
            "description":  item.get("description", ""),
            "releaseValue": release_value,
            "site":         item.get("site_id", ""),
            "criticality":  criticality,
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/kpi-summary", response_model=KpiSummary, summary="Aggregate KPI counts and total inventory value")
async def kpi_summary(settings: SettingsDep, _user: UserDep) -> KpiSummary:
    records = await fetch_inventory(settings)
    if not records:
        logger.warning("No inventory records returned from Maximo — returning zeros")
    data = compute_kpi_summary(records)
    return KpiSummary(**data)


@router.get("/inventory-by-status", response_model=InventoryByStatus, summary="Item count and value split by inventory health status")
async def inventory_by_status(settings: SettingsDep, _user: UserDep) -> InventoryByStatus:
    records = await fetch_inventory(settings)
    buckets_data = compute_inventory_by_status(records)
    return InventoryByStatus(buckets=[StatusBucket(**b) for b in buckets_data])


@router.get("/top-items-by-risk", response_model=TopItemsByRisk, summary="Top items most at risk of stockout")
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
    return TopItemsByRisk(items=[TopItem(**i) for i in items_data])


@router.get("/forecast-accuracy/detail", response_model=ForecastAccuracy, summary="Full forecast accuracy with overall MAPE")
def forecast_accuracy_detail(_user: UserDep) -> ForecastAccuracy:
    return ForecastAccuracy(rows=FORECAST_ROWS, overall_mape=OVERALL_MAPE)


@router.get("/recommendations", response_model=list[Recommendation], summary="Prioritised inventory optimisation recommendations")
def recommendations(_user: UserDep) -> list[Recommendation]:
    return RECOMMENDATIONS
