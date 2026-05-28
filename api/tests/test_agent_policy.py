"""
Unit tests for the agentic auto-apply policy engine.
"""
import os
import pytest

os.environ["AGENT_AUTO_APPLY_ENABLED"] = "true"
os.environ["AGENT_MAX_DELTA_WC"] = "5000"
os.environ["AGENT_ALLOWED_CRITICALITIES"] = "LOW"
os.environ["AGENT_ALLOWED_TYPES"] = "ROP,SS,EOQ"

from app.agent.policy import evaluate  # noqa: E402
from app.recommendations.models import (  # noqa: E402
    RecommendationDetail, Rationale, VendorInfo,
)


def _make_rec(*, criticality="LOW", type_="ROP", delta_wc=1000.0, status="NEW",
              recommended_value=18):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return RecommendationDetail(
        rec_id="REC-001", item_id="PUMP-001",
        item_description="Pump", warehouse_id="BEDFORD",
        type=type_, criticality=criticality,
        current_value=32, recommended_value=recommended_value,
        delta_working_capital=delta_wc, confidence=0.9,
        status=status, version=1, created_at=now,
        wc_release=delta_wc, stock_out_risk_change_pct=0,
        model_version="test", expires_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat().replace("+00:00", "Z"),
        rationale=Rationale(
            demand_pattern="intermittent", adi=1.7, cv_squared=0.6,
            twelve_month_mean_qty=84, lead_time_days_mean=14, lead_time_days_std=4,
            service_level_target=0.99, summary_text="t",
        ),
        feature_contributions=[], vendor=VendorInfo(
            vendor_id="V1", name="Acme",
            mean_lead_days=14, std_lead_days=4, on_time_pct=0.9,
            unit_cost=260, holding_cost_pct=0.22, order_cost=85,
        ),
        linked_assets=[], audit=[],
    )


def test_policy_approves_low_crit_below_threshold():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    decision = evaluate(_make_rec(criticality="LOW", delta_wc=1000), open_po_qty=0)
    assert decision.approved is True


def test_policy_rejects_high_crit():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    decision = evaluate(_make_rec(criticality="HIGH", delta_wc=1000), open_po_qty=0)
    assert decision.approved is False
    assert "criticality" in decision.reason.lower()


def test_policy_rejects_above_delta_threshold():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    decision = evaluate(_make_rec(criticality="LOW", delta_wc=10_000), open_po_qty=0)
    assert decision.approved is False
    assert "threshold" in decision.reason.lower()


def test_policy_rejects_when_open_po_too_large():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    # recommended_value=18, open_po_qty=20 > 9 (50% of 18)
    decision = evaluate(
        _make_rec(criticality="LOW", delta_wc=1000, recommended_value=18),
        open_po_qty=20,
    )
    assert decision.approved is False
    assert "po" in decision.reason.lower()


def test_policy_rejects_when_status_not_new():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    decision = evaluate(_make_rec(status="APPROVED"), open_po_qty=0)
    assert decision.approved is False
    assert "new" in decision.reason.lower()
