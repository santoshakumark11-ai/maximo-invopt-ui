"""
Seed data for metrics that can't be derived from MXINVENTORY alone:
  - Forecast accuracy (MAPE/MAE/bias per item — normally from a forecasting engine)
  - Recommendations (action items — normally from an optimisation engine)

These are plausible static fixtures that match the inventory item numbers
returned by Maximo.  They are blended with real data: the KPI counts and
top-items list come from live MXINVENTORY, while these two endpoints use
the seed data.

When Phase 2 ships a forecasting engine, swap these out.
"""
from app.metrics.models import ForecastAccuracyRow, Recommendation

FORECAST_ROWS: list[ForecastAccuracyRow] = [
    ForecastAccuracyRow(
        item_num="1001-BEARING",
        description="Ball Bearing 6205",
        site_id="BEDFORD",
        mape=8.2,
        mae=4.1,
        bias=-1.3,
        trend="improving",
    ),
    ForecastAccuracyRow(
        item_num="2034-PUMP",
        description="Centrifugal Pump 2\" 316SS",
        site_id="BEDFORD",
        mape=22.7,
        mae=1.8,
        bias=3.4,
        trend="degrading",
    ),
    ForecastAccuracyRow(
        item_num="3110-GASKET",
        description="Spiral Wound Gasket DN50",
        site_id="BEDFORD",
        mape=11.5,
        mae=15.2,
        bias=-0.5,
        trend="stable",
    ),
    ForecastAccuracyRow(
        item_num="4002-VALVE",
        description="Gate Valve 4\" Class 150",
        site_id="NORTHGATE",
        mape=5.9,
        mae=0.9,
        bias=0.1,
        trend="improving",
    ),
    ForecastAccuracyRow(
        item_num="4019-VALVE",
        description="Globe Valve 2\" Class 300",
        site_id="NORTHGATE",
        mape=14.3,
        mae=2.2,
        bias=2.1,
        trend="stable",
    ),
    ForecastAccuracyRow(
        item_num="5200-FILTER",
        description="Oil Filter Element P551000",
        site_id="BEDFORD",
        mape=6.1,
        mae=8.0,
        bias=-0.8,
        trend="improving",
    ),
    ForecastAccuracyRow(
        item_num="6300-BELT",
        description="V-Belt B-Section B68",
        site_id="BEDFORD",
        mape=19.8,
        mae=6.3,
        bias=4.5,
        trend="degrading",
    ),
    ForecastAccuracyRow(
        item_num="7001-SEAL",
        description="Mechanical Seal 1.5\"",
        site_id="NORTHGATE",
        mape=9.0,
        mae=1.1,
        bias=-0.2,
        trend="stable",
    ),
]

OVERALL_MAPE: float = round(
    sum(r.mape for r in FORECAST_ROWS) / len(FORECAST_ROWS), 1
)

RECOMMENDATIONS: list[Recommendation] = [
    Recommendation(
        id="REC-001",
        item_num="2034-PUMP",
        description="Centrifugal Pump 2\" 316SS",
        site_id="BEDFORD",
        action="Increase Reorder Point",
        rationale=(
            "Forecast MAPE of 22.7% combined with 14-day lead time creates "
            "stockout exposure.  Raising reorder point from 2 to 4 units "
            "covers 2σ demand variability."
        ),
        priority="high",
        estimated_saving=18_400.0,
    ),
    Recommendation(
        id="REC-002",
        item_num="6300-BELT",
        description="V-Belt B-Section B68",
        site_id="BEDFORD",
        action="Increase Reorder Point",
        rationale=(
            "Degrading forecast accuracy (MAPE 19.8%, bias +4.5) suggests "
            "demand is growing.  Safety stock needs uplift to match Q3 usage."
        ),
        priority="high",
        estimated_saving=4_200.0,
    ),
    Recommendation(
        id="REC-003",
        item_num="3110-GASKET",
        description="Spiral Wound Gasket DN50",
        site_id="BEDFORD",
        action="Reduce Order Quantity",
        rationale=(
            "Current balance is 3× annual usage.  Reducing EOQ by 40% will "
            "draw down excess inventory over 18 months without service risk."
        ),
        priority="medium",
        estimated_saving=6_750.0,
    ),
    Recommendation(
        id="REC-004",
        item_num="4019-VALVE",
        description="Globe Valve 2\" Class 300",
        site_id="NORTHGATE",
        action="Consolidate Storerooms",
        rationale=(
            "Same item held at both BEDFORD and NORTHGATE with combined excess "
            "of 12 units.  Pooling stock at BEDFORD saves ~$9k in carrying cost."
        ),
        priority="medium",
        estimated_saving=9_100.0,
    ),
    Recommendation(
        id="REC-005",
        item_num="5200-FILTER",
        description="Oil Filter Element P551000",
        site_id="BEDFORD",
        action="Switch to Vendor-Managed Inventory",
        rationale=(
            "Supplier offers VMI with daily replenishment.  Eliminates $2.3k "
            "annual ordering cost and reduces average on-hand by 30%."
        ),
        priority="low",
        estimated_saving=2_300.0,
    ),
]
