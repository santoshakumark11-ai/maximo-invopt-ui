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
    from app.recommendations import service as rec_service

    records = await fetch_inventory(settings)
    kpi = compute_kpi_summary(records)

    total_items = kpi["total_items"]
    healthy = total_items - kpi["below_reorder"] - kpi["stockout_risk"]
    service_level = round(healthy / total_items * 100, 1) if total_items > 0 else 0.0

    # Count open recommendations (NEW or PENDING)
    open_recs = sum(
        1 for r in await rec_service.list_all()
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

    Q1.2 — derived from actual APPLIED recommendations:
        for each of the last 12 months, sum delta_working_capital over recs
        whose updated_at (= APPLIED moment) falls in that month, then return
        the rolling cumulative total.

    Falls back to the legacy synthetic series when persistence is disabled
    or when no APPLIED recommendations exist yet (otherwise the chart would
    be flat at zero on first run).
    """
    from datetime import date, datetime, timedelta, timezone

    real = await _working_capital_trend_from_db()
    if real is not None:
        return real

    # Legacy fallback — synthetic series anchored to current inventory value.
    records = await fetch_inventory(settings)
    kpi = compute_kpi_summary(records)
    current_wc = kpi["total_value"] * 0.35

    today = date.today()
    points = []
    for i in range(11, -1, -1):
        month_date = (today.replace(day=1) - timedelta(days=i * 30))
        period = month_date.strftime("%Y-%m")
        seasonal = 1.0 - 0.04 * math.sin(math.pi * month_date.month / 12)
        growth   = 1.0 + 0.08 * (i / 11)
        value    = round(current_wc * seasonal * growth, 2)
        points.append({"period": period, "value": value})

    return points


async def _working_capital_trend_from_db():
    """
    Build the cumulative working-capital-release curve from the
    recommendations table.  Returns None when persistence is disabled OR
    when no APPLIED rows exist (caller falls back to synthetic).
    """
    from app import db
    if not db.is_enabled():
        return None
    try:
        from sqlalchemy import select
        from app.models_db import Recommendation
        from collections import defaultdict
        from datetime import datetime, timedelta, timezone

        async with db.session_scope() as s:
            stmt = (
                select(Recommendation.delta_working_capital,
                       Recommendation.updated_at,
                       Recommendation.status)
                .where(Recommendation.status == "APPLIED")
            )
            rows = (await s.execute(stmt)).all()

        if not rows:
            return None

        bucket: dict[str, float] = defaultdict(float)
        for delta, ts, _status in rows:
            month = ts.strftime("%Y-%m") if ts else "unknown"
            bucket[month] += float(delta or 0.0)

        # Build the last 12 months ending today, oldest first.
        today = datetime.now(timezone.utc).date().replace(day=1)
        months: list[str] = []
        cur = today
        for _ in range(12):
            months.append(cur.strftime("%Y-%m"))
            prev = cur - timedelta(days=1)
            cur  = prev.replace(day=1)
        months.reverse()

        cumulative = 0.0
        out: list[dict] = []
        for m in months:
            cumulative += bucket.get(m, 0.0)
            out.append({"period": m, "value": round(cumulative, 2)})
        return out
    except Exception:
        return None


@router.get("/recommendations-by-status", summary="Recommendation counts by status (frontend-compatible)")
async def recommendations_by_status(_user: UserDep) -> list[dict]:
    """
    Returns StatusMixItem[] shape: [{ status, count }, ...]

    Sourced from whichever store is active (DB if persistence_enabled, else
    in-memory).
    """
    from app.recommendations import service as rec_service
    from collections import Counter

    counts: Counter = Counter(r.status for r in await rec_service.list_all())
    # Include all known statuses even if count is 0
    all_statuses = ["NEW", "PENDING", "APPROVED", "APPLIED", "REJECTED"]
    return [{"status": s, "count": counts.get(s, 0)} for s in all_statuses]


@router.get("/forecast-accuracy", summary="Forecast accuracy rows (frontend-compatible)")
async def forecast_accuracy_compat(_user: UserDep) -> list[dict]:
    """
    Returns ForecastAccuracyRow[] shape: [{ itemId, description, wape, bias }, ...]

    Q1.2 — when forecast_backtests has rows, return the latest backtest per
    demand pattern.  Falls back to the legacy static seed otherwise.
    """
    from app import db
    if db.is_enabled():
        try:
            from sqlalchemy import select, desc
            from app.models_db import ForecastBacktest
            async with db.session_scope() as s:
                # Latest run wins (we use it as a proxy for "current model").
                run_q = (
                    select(ForecastBacktest.run_id)
                    .order_by(desc(ForecastBacktest.as_of))
                    .limit(1)
                )
                run_id = (await s.execute(run_q)).scalar()
                if run_id:
                    rows_q = select(ForecastBacktest).where(ForecastBacktest.run_id == run_id)
                    rows = (await s.execute(rows_q)).scalars().all()
                    if rows:
                        return [
                            {
                                "itemId":      r.pattern.upper(),
                                "description": f"{r.n_items} items, model={r.model_version}",
                                "wape":        round(r.wape, 2),
                                "bias":        round(r.bias, 2),
                            }
                            for r in rows
                        ]
        except Exception:
            pass

    # Legacy static seed fallback.
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
