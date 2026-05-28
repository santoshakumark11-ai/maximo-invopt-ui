"""
DB-backed repository for recommendations.

Translates between the SQLAlchemy ORM rows and the Pydantic
RecommendationDetail / RecommendationListItem the API exposes.

This file is imported only when `db.is_enabled()` is true; callers should go
through app.recommendations.service which routes to either the DB repo or
the in-memory store at runtime.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app import db
from app.recommendations.models import (
    AuditEvent, FeatureContribution, LinkedAsset, Rationale,
    RecommendationDetail, VendorInfo,
)

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import select, delete
    from app.models_db import Recommendation as ORM, RecommendationFeature as ORMFeat, AuditEvent as ORMAudit
    _SA_OK = True
except Exception:
    _SA_OK = False


# ── Serialisation: Pydantic ↔ ORM ─────────────────────────────────────────────

def _iso(ts: datetime | str) -> str:
    if isinstance(ts, str):
        return ts
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_pydantic(orm: "ORM", features: list["ORMFeat"], audit: list["ORMAudit"]) -> RecommendationDetail:
    rationale = Rationale(**orm.rationale_json)
    vendor    = VendorInfo(**orm.vendor_json) if orm.vendor_json else VendorInfo(
        vendor_id="UNKNOWN", name="—",
        mean_lead_days=14, std_lead_days=4, on_time_pct=0.85,
        unit_cost=0.0, holding_cost_pct=0.2, order_cost=75.0,
    )
    linked_assets = [LinkedAsset(**a) for a in (orm.linked_assets_json or [])]
    feat_list = [
        FeatureContribution(
            name=f.name,
            value=f.value_num if f.value_num is not None else f.value_str,
            contribution=f.contribution,
        )
        for f in features
    ]
    audit_list = [
        AuditEvent(
            ts=_iso(a.ts),
            actor=a.principal,
            event=a.action,   # type: ignore[arg-type]
            detail=a.detail,
        )
        for a in audit
    ]
    current_value     = orm.current_value_num     if orm.current_value_num     is not None else (orm.current_value_str     or "")
    recommended_value = orm.recommended_value_num if orm.recommended_value_num is not None else (orm.recommended_value_str or "")

    return RecommendationDetail(
        rec_id=orm.rec_id,
        item_id=orm.item_id,
        item_description=orm.item_description,
        warehouse_id=orm.warehouse_id,
        type=orm.type,                # type: ignore[arg-type]
        criticality=orm.criticality,  # type: ignore[arg-type]
        current_value=current_value,
        recommended_value=recommended_value,
        delta_working_capital=orm.delta_working_capital,
        confidence=orm.confidence,
        status=orm.status,            # type: ignore[arg-type]
        version=orm.version,
        created_at=_iso(orm.created_at),
        wc_release=orm.wc_release,
        stock_out_risk_change_pct=orm.stock_out_risk_change_pct,
        model_version=orm.model_version,
        expires_at=_iso(orm.expires_at),
        rationale=rationale,
        feature_contributions=feat_list,
        vendor=vendor,
        linked_assets=linked_assets,
        audit=audit_list,
    )


def _from_pydantic(rec: RecommendationDetail) -> tuple["ORM", list["ORMFeat"]]:
    cur_num = rec.current_value     if isinstance(rec.current_value, (int, float))     else None
    cur_str = rec.current_value     if isinstance(rec.current_value, str)              else None
    rec_num = rec.recommended_value if isinstance(rec.recommended_value, (int, float)) else None
    rec_str = rec.recommended_value if isinstance(rec.recommended_value, str)          else None

    orm = ORM(
        rec_id=rec.rec_id,
        item_id=rec.item_id,
        item_description=rec.item_description,
        warehouse_id=rec.warehouse_id,
        type=rec.type,
        criticality=rec.criticality,
        current_value_num=cur_num,
        current_value_str=cur_str,
        recommended_value_num=rec_num,
        recommended_value_str=rec_str,
        delta_working_capital=rec.delta_working_capital,
        wc_release=rec.wc_release,
        stock_out_risk_change_pct=rec.stock_out_risk_change_pct,
        confidence=rec.confidence,
        status=rec.status,
        version=rec.version,
        model_version=rec.model_version,
        rationale_json=rec.rationale.model_dump(by_alias=False),
        vendor_json=rec.vendor.model_dump(by_alias=False),
        linked_assets_json=[a.model_dump(by_alias=False) for a in rec.linked_assets],
        created_at=_parse_ts(rec.created_at),
        expires_at=_parse_ts(rec.expires_at),
    )
    feats = [
        ORMFeat(
            rec_id=rec.rec_id,
            name=f.name,
            value_num=f.value if isinstance(f.value, (int, float)) else None,
            value_str=f.value if isinstance(f.value, str) else None,
            contribution=f.contribution,
        )
        for f in rec.feature_contributions
    ]
    return orm, feats


def _parse_ts(ts: str) -> datetime:
    """ISO 'Z' → datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ── Public async API ──────────────────────────────────────────────────────────

async def replace_all(records: list[RecommendationDetail]) -> int:
    """Atomically replace every recommendation row with the new list."""
    if not _SA_OK:
        return 0
    async with db.session_scope() as s:
        await s.execute(delete(ORM))   # cascades to features
        for rec in records:
            orm, feats = _from_pydantic(rec)
            s.add(orm)
            for f in feats:
                s.add(f)
    return len(records)


async def get_all() -> list[RecommendationDetail]:
    if not _SA_OK:
        return []
    async with db.session_scope() as s:
        result = await s.execute(select(ORM))
        orm_recs = list(result.scalars().all())
        # Fetch features for each (small numbers — N+1 is fine at this scale).
        out: list[RecommendationDetail] = []
        for orm in orm_recs:
            feats_q = await s.execute(select(ORMFeat).where(ORMFeat.rec_id == orm.rec_id))
            audit_q = await s.execute(
                select(ORMAudit)
                .where(ORMAudit.subject == orm.rec_id)
                .order_by(ORMAudit.event_id.asc())
            )
            out.append(_to_pydantic(orm, list(feats_q.scalars().all()), list(audit_q.scalars().all())))
    return out


async def get_one(rec_id: str) -> Optional[RecommendationDetail]:
    if not _SA_OK:
        return None
    async with db.session_scope() as s:
        result = await s.execute(select(ORM).where(ORM.rec_id == rec_id))
        orm = result.scalars().first()
        if orm is None:
            return None
        feats_q = await s.execute(select(ORMFeat).where(ORMFeat.rec_id == rec_id))
        audit_q = await s.execute(
            select(ORMAudit).where(ORMAudit.subject == rec_id)
            .order_by(ORMAudit.event_id.asc())
        )
        return _to_pydantic(orm, list(feats_q.scalars().all()), list(audit_q.scalars().all()))


async def update_status(
    rec_id: str, new_status: str, actor: str, detail: Optional[str] = None,
) -> Optional[RecommendationDetail]:
    if not _SA_OK:
        return None
    from app import audit  # local import: avoid cycles
    async with db.session_scope() as s:
        result = await s.execute(select(ORM).where(ORM.rec_id == rec_id))
        orm = result.scalars().first()
        if orm is None:
            return None
        before = {"status": orm.status, "version": orm.version}
        orm.status = new_status
        orm.updated_at = datetime.now(timezone.utc)
    # Audit write committed in its own session for clean isolation.
    await audit.write_event(
        principal=actor, action=new_status, subject=rec_id,
        before_state=before, after_state={"status": new_status}, detail=detail,
    )
    return await get_one(rec_id)


async def edit_recommendation(
    rec_id: str, recommended_value: float, justification: str,
    expected_version: int, actor: str,
) -> Optional[RecommendationDetail]:
    """Returns None on version conflict (409) OR not-found."""
    if not _SA_OK:
        return None
    from app import audit
    async with db.session_scope() as s:
        result = await s.execute(select(ORM).where(ORM.rec_id == rec_id))
        orm = result.scalars().first()
        if orm is None:
            return None
        if orm.version != expected_version:
            return None
        before = {
            "recommended_value": orm.recommended_value_num,
            "version": orm.version,
        }
        orm.recommended_value_num = recommended_value
        orm.recommended_value_str = None
        orm.version += 1
        orm.updated_at = datetime.now(timezone.utc)
    await audit.write_event(
        principal=actor, action="EDITED", subject=rec_id,
        before_state=before,
        after_state={"recommended_value": recommended_value, "version": expected_version + 1},
        detail=justification,
    )
    return await get_one(rec_id)


async def write_initial_audit(rec_id: str) -> None:
    """Convenience: log CREATED + NOTIFIED for a freshly seeded recommendation."""
    from app import audit
    await audit.write_event(principal="system", action="CREATED", subject=rec_id)
    await audit.write_event(principal="system", action="NOTIFIED", subject=rec_id,
                            detail="Sent to planner inbox")
