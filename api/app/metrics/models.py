"""
Pydantic response models for the /v1/metrics endpoints.
"""
from pydantic import BaseModel


# ── KPI Summary ───────────────────────────────────────────────────────────────

class KpiSummary(BaseModel):
    total_items: int
    total_value: float
    currency: str = "USD"
    below_reorder: int
    stockout_risk: int
    excess_stock: int


# ── Inventory By Status ───────────────────────────────────────────────────────

class StatusBucket(BaseModel):
    status: str          # e.g. "OK", "Below Reorder", "Stockout Risk", "Excess"
    count: int
    value: float


class InventoryByStatus(BaseModel):
    buckets: list[StatusBucket]
    currency: str = "USD"


# ── Top Items By Reorder Risk ─────────────────────────────────────────────────

class TopItem(BaseModel):
    item_num: str
    description: str
    site_id: str
    current_bal: float
    reorder_point: float
    unit_cost: float
    currency: str = "USD"
    risk_score: float        # 0–100; higher = more critical


class TopItemsByRisk(BaseModel):
    items: list[TopItem]


# ── Forecast Accuracy ─────────────────────────────────────────────────────────

class ForecastAccuracyRow(BaseModel):
    item_num: str
    description: str
    site_id: str
    mape: float              # Mean Absolute Percentage Error (0–100)
    mae: float               # Mean Absolute Error (demand units)
    bias: float              # Signed error — positive = over-forecasted
    trend: str               # "improving" | "stable" | "degrading"


class ForecastAccuracy(BaseModel):
    rows: list[ForecastAccuracyRow]
    overall_mape: float


# ── Recommendations ───────────────────────────────────────────────────────────

class Recommendation(BaseModel):
    id: str
    item_num: str
    description: str
    site_id: str
    action: str              # "Increase Reorder Point" | "Reduce Order Qty" | etc.
    rationale: str
    priority: str            # "high" | "medium" | "low"
    estimated_saving: float
    currency: str = "USD"
