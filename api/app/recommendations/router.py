"""
Recommendations router — /v1/recommendations

GET    /v1/recommendations                  list with filter/sort/page
GET    /v1/recommendations/{rec_id}         single recommendation detail
PATCH  /v1/recommendations/{rec_id}         planner edit (INVADMIN)
POST   /v1/recommendations/{rec_id}/approve approve
POST   /v1/recommendations/{rec_id}/reject  reject
POST   /v1/recommendations:bulk-approve     bulk approve (INVMGR+)
POST   /v1/recommendations:bulk-reject      bulk reject  (INVMGR+)
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import CurrentUser, get_current_user
from app.recommendations import store as rec_store
from app.recommendations.models import (
    ApprovePayload, BulkApprovePayload, BulkRejectPayload,
    BulkResultItem, BulkResultSummary, EditPayload,
    RecommendationDetail, RecommendationListItem,
    RecommendationListResponse, RejectPayload,
)

logger = logging.getLogger(__name__)
router = APIRouter()

UserDep = Annotated[CurrentUser, Depends(get_current_user)]
_NOW = lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")  # noqa: E731


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_list_item(rec: RecommendationDetail) -> RecommendationListItem:
    return RecommendationListItem(
        rec_id=rec.rec_id, item_id=rec.item_id,
        item_description=rec.item_description, warehouse_id=rec.warehouse_id,
        type=rec.type, criticality=rec.criticality,
        current_value=rec.current_value, recommended_value=rec.recommended_value,
        delta_working_capital=rec.delta_working_capital, confidence=rec.confidence,
        status=rec.status, version=rec.version, created_at=rec.created_at,
    )


def _sort_key(rec: RecommendationListItem, field: str) -> float | str:
    if field == "delta":       return rec.delta_working_capital
    if field == "confidence":  return rec.confidence
    if field == "status":      return rec.status
    if field == "criticality":
        return {"HIGH": 0, "MED": 1, "LOW": 2}.get(rec.criticality, 9)
    return rec.rec_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=RecommendationListResponse,
            response_model_by_alias=True,
            summary="List recommendations")
def list_recommendations(
    _user: UserDep,
    status_filter: Annotated[Optional[str], Query(alias="status")] = None,
    type_filter:   Annotated[Optional[str], Query(alias="type")]   = None,
    crit_filter:   Annotated[Optional[str], Query(alias="criticality")] = None,
    item:          Annotated[Optional[str], Query()] = None,
    q:             Annotated[Optional[str], Query()] = None,
    page:          Annotated[int, Query(ge=1)] = 1,
    page_size:     Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
    sort:          Annotated[str, Query(
        pattern=r"^(recId|delta|confidence|status|criticality):(asc|desc)$"
    )] = "delta:desc",
) -> RecommendationListResponse:
    items = [_to_list_item(r) for r in rec_store.get_all()]

    if status_filter:
        allowed = {s.upper() for s in status_filter.split(",") if s}
        items = [i for i in items if i.status in allowed]
    if type_filter:
        allowed_t = {t.upper() for t in type_filter.split(",") if t}
        items = [i for i in items if i.type in allowed_t]
    if crit_filter:
        allowed_c = {c.upper() for c in crit_filter.split(",") if c}
        items = [i for i in items if i.criticality in allowed_c]
    if item:
        items = [i for i in items if i.item_id.lower() == item.lower()]
    if q:
        q_l = q.lower()
        items = [i for i in items if q_l in i.item_id.lower()
                 or q_l in i.item_description.lower()
                 or q_l in i.warehouse_id.lower()]

    sort_field, sort_dir = sort.split(":")
    items.sort(key=lambda r: _sort_key(r, sort_field), reverse=(sort_dir == "desc"))

    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    return RecommendationListResponse(
        items=items[start: start + page_size],
        page=page, page_size=page_size,
        total_items=total, total_pages=total_pages, as_of=_NOW(),
    )


@router.get("/{rec_id}", response_model=RecommendationDetail,
            response_model_by_alias=True,
            summary="Get recommendation detail")
def get_recommendation(rec_id: str, _user: UserDep) -> RecommendationDetail:
    rec = rec_store.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")
    return rec


@router.patch("/{rec_id}", response_model=RecommendationDetail,
              response_model_by_alias=True,
              summary="Edit recommended value (INVADMIN)")
def edit_recommendation(
    rec_id: str,
    payload: EditPayload,
    user: UserDep,
) -> RecommendationDetail:
    if len(payload.justification) < 50:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="justification must be at least 50 characters")
    rec = rec_store.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")
    updated = rec_store.edit_recommendation(
        rec_id,
        recommended_value=payload.recommended_value,
        justification=payload.justification,
        expected_version=payload.expected_version,
        actor=user.username,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Version conflict — recommendation was edited concurrently")
    return updated


@router.post("/{rec_id}/approve", response_model=RecommendationDetail,
             response_model_by_alias=True,
             summary="Approve a recommendation")
def approve_recommendation(
    rec_id: str, payload: ApprovePayload, user: UserDep,
) -> RecommendationDetail:
    rec = rec_store.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")
    if rec.status not in ("NEW", "PENDING"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Cannot approve a recommendation with status {rec.status}")
    return rec_store.update_status(rec_id, "APPROVED", actor=user.username,
                                   detail=payload.justification)


@router.post("/{rec_id}/reject", response_model=RecommendationDetail,
             response_model_by_alias=True,
             summary="Reject a recommendation")
def reject_recommendation(
    rec_id: str, payload: RejectPayload, user: UserDep,
) -> RecommendationDetail:
    rec = rec_store.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")
    if rec.status in ("APPLIED", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Cannot reject a recommendation with status {rec.status}")
    return rec_store.update_status(rec_id, "REJECTED", actor=user.username,
                                   detail=payload.reason)


@router.post(":bulk-approve", response_model=BulkResultSummary,
             response_model_by_alias=True,
             summary="Bulk approve (INVMGR+)")
def bulk_approve(payload: BulkApprovePayload, user: UserDep) -> BulkResultSummary:
    succeeded, failed = [], []
    for rid in payload.rec_ids:
        rec = rec_store.get_one(rid)
        if rec is None:
            failed.append(BulkResultItem(rec_id=rid, error="Not found"))
        elif rec.status not in ("NEW", "PENDING"):
            failed.append(BulkResultItem(rec_id=rid, error=f"Status is {rec.status}"))
        else:
            rec_store.update_status(rid, "APPROVED", actor=user.username,
                                    detail=payload.justification)
            succeeded.append(rid)
    return BulkResultSummary(succeeded=succeeded, failed=failed)


@router.post(":bulk-reject", response_model=BulkResultSummary,
             response_model_by_alias=True,
             summary="Bulk reject (INVMGR+)")
def bulk_reject(payload: BulkRejectPayload, user: UserDep) -> BulkResultSummary:
    succeeded, failed = [], []
    for rid in payload.rec_ids:
        rec = rec_store.get_one(rid)
        if rec is None:
            failed.append(BulkResultItem(rec_id=rid, error="Not found"))
        elif rec.status in ("APPLIED", "REJECTED"):
            failed.append(BulkResultItem(rec_id=rid, error=f"Status is {rec.status}"))
        else:
            rec_store.update_status(rid, "REJECTED", actor=user.username,
                                    detail=payload.reason)
            succeeded.append(rid)
    return BulkResultSummary(succeeded=succeeded, failed=failed)
