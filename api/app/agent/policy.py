"""
Auto-apply policy engine.

A recommendation is auto-approvable when ALL of:
    1. agent_auto_apply_enabled is True.
    2. rec.criticality is in agent_allowed_criticalities.
    3. rec.type is in agent_allowed_types.
    4. abs(rec.delta_working_capital) <= agent_max_delta_wc.
    5. rec.status == "NEW".
    6. No conflicting open PO exists for the same item (cross-check).

The cross-check against open POs (step 6) is the "agent reasoning" step —
it prevents the agent from auto-applying a ROP reduction when a large PO
is already in transit.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.recommendations.models import RecommendationDetail

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    approved: bool
    reason: str


def evaluate(rec: RecommendationDetail, *, open_po_qty: float = 0.0) -> PolicyDecision:
    """
    Evaluate whether a recommendation qualifies for auto-apply.

    open_po_qty: total quantity on open (not-yet-received) POs for this item.
    """
    settings = get_settings()

    if not settings.agent_auto_apply_enabled:
        return PolicyDecision(approved=False, reason="agent disabled")

    if rec.status != "NEW":
        return PolicyDecision(approved=False, reason=f"status is {rec.status}, not NEW")

    allowed_crits = {c.strip().upper() for c in settings.agent_allowed_criticalities.split(",")}
    if rec.criticality not in allowed_crits:
        return PolicyDecision(approved=False,
                              reason=f"criticality {rec.criticality} not in {allowed_crits}")

    allowed_types = {t.strip().upper() for t in settings.agent_allowed_types.split(",")}
    if rec.type not in allowed_types:
        return PolicyDecision(approved=False,
                              reason=f"type {rec.type} not in {allowed_types}")

    if abs(rec.delta_working_capital) > settings.agent_max_delta_wc:
        return PolicyDecision(approved=False,
                              reason=f"|delta_wc| {abs(rec.delta_working_capital):.0f} > "
                                     f"threshold {settings.agent_max_delta_wc:.0f}")

    # Cross-check: if a large PO is in transit, don't reduce ROP.
    if rec.type == "ROP" and open_po_qty > 0:
        try:
            recommended = float(rec.recommended_value)
        except (TypeError, ValueError):
            recommended = 0.0
        if open_po_qty > recommended * 0.5:
            return PolicyDecision(
                approved=False,
                reason=f"open PO qty {open_po_qty:.0f} > 50% of recommended ROP "
                       f"{recommended:.0f} — deferring to planner",
            )

    return PolicyDecision(approved=True, reason="policy passed")
