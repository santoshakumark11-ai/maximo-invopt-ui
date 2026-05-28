"""
Pydantic models for /v1/recommendations endpoints.
All models use camelCase JSON aliases to match the TypeScript frontend.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

RecStatus    = Literal["NEW", "PENDING", "APPROVED", "APPLIED", "REJECTED",
                       "FAILED", "SUPERSEDED"]
RecType      = Literal["ROP", "SS", "EOQ", "SUB", "WRITEOFF"]
Criticality  = Literal["HIGH", "MED", "LOW"]
AuditEvent_T = Literal["CREATED", "NOTIFIED", "VIEWED", "EDITED",
                        "APPROVED", "REJECTED", "APPLIED", "FAILED"]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# ── List item ──────────────────────────────────────────────────────────────────

class RecommendationListItem(CamelModel):
    rec_id:                str
    item_id:               str
    item_description:      str
    warehouse_id:          str
    type:                  RecType
    criticality:           Criticality
    current_value:         float | str
    recommended_value:     float | str
    delta_working_capital: float
    confidence:            float
    status:                RecStatus
    version:               int
    created_at:            str


class RecommendationListResponse(CamelModel):
    items:       list[RecommendationListItem]
    page:        int
    page_size:   int
    total_items: int
    total_pages: int
    as_of:       str


# ── Detail ─────────────────────────────────────────────────────────────────────

class FeatureContribution(CamelModel):
    name:         str
    value:        float | str
    contribution: float


class Rationale(CamelModel):
    demand_pattern:        Literal["smooth", "intermittent", "erratic", "lumpy"]
    adi:                   float
    cv_squared:            float
    twelve_month_mean_qty: float
    lead_time_days_mean:   float
    lead_time_days_std:    float
    service_level_target:  float
    summary_text:          str


class VendorInfo(CamelModel):
    vendor_id:        str
    name:             str
    mean_lead_days:   float
    std_lead_days:    float
    on_time_pct:      float
    unit_cost:        float
    holding_cost_pct: float
    order_cost:       float


class LinkedAsset(CamelModel):
    asset_id:    str
    description: str
    criticality: Criticality


class AuditEvent(CamelModel):
    ts:     str
    actor:  str
    event:  AuditEvent_T
    detail: Optional[str] = None


class RecommendationDetail(RecommendationListItem):
    rationale:                 Rationale
    feature_contributions:     list[FeatureContribution]
    vendor:                    VendorInfo
    linked_assets:             list[LinkedAsset]
    audit:                     list[AuditEvent]
    wc_release:                float
    stock_out_risk_change_pct: float
    model_version:             str
    expires_at:                str


# ── Request bodies ─────────────────────────────────────────────────────────────

class ApprovePayload(CamelModel):
    justification: Optional[str] = None


class RejectPayload(CamelModel):
    reason: str


class EditPayload(CamelModel):
    recommended_value: float
    justification:     str
    expected_version:  int


class BulkApprovePayload(CamelModel):
    rec_ids:       list[str]
    justification: Optional[str] = None


class BulkRejectPayload(CamelModel):
    rec_ids: list[str]
    reason:  str


class BulkResultItem(CamelModel):
    rec_id: str
    error:  Optional[str] = None


class BulkResultSummary(CamelModel):
    succeeded: list[str]
    failed:    list[BulkResultItem]
