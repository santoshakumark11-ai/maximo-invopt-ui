"""
Planner-feedback capture (Q1.2 shadow mode).

Whenever a planner approves, rejects, or edits a recommendation, we record
the raw confidence + features + their decision into the planner_feedback
table.  The calibrator model itself (isotonic / LightGBM mapping raw
confidence → P(approved)) is Q2 work — this module is the data-collection
half that has to run starting now so the calibrator has labels by then.

Best-effort: silent no-op when persistence is disabled.
"""
from __future__ import annotations

import logging
from typing import Optional

from app import db
from app.recommendations.models import RecommendationDetail

logger = logging.getLogger(__name__)


async def record_planner_decision(
    *,
    rec: RecommendationDetail,
    principal: str,
    decision: str,                 # APPROVED | REJECTED | EDITED
    override_value: Optional[float] = None,
    reason: Optional[str] = None,
) -> None:
    if not db.is_enabled():
        return

    try:
        from app.models_db import PlannerFeedback
        features = {fc.name: fc.value for fc in rec.feature_contributions}
        recommended = None
        if isinstance(rec.recommended_value, (int, float)):
            recommended = float(rec.recommended_value)
        async with db.session_scope() as s:
            s.add(PlannerFeedback(
                rec_id=rec.rec_id,
                principal=principal,
                decision=decision,
                raw_confidence=rec.confidence,
                recommended_value=recommended,
                override_value=override_value,
                reason_or_justification=reason,
                features_json={
                    "features":       features,
                    "criticality":    rec.criticality,
                    "demand_pattern": rec.rationale.demand_pattern,
                    "adi":            rec.rationale.adi,
                    "cv_squared":     rec.rationale.cv_squared,
                    "service_level":  rec.rationale.service_level_target,
                    "model_version":  rec.model_version,
                    "type":           rec.type,
                },
            ))
    except Exception as exc:
        logger.warning("Planner feedback capture failed for %s: %s", rec.rec_id, exc)
