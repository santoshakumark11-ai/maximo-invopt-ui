"""
Unit tests for the LLM gateway — mock driver path.
"""
import os
import pytest

os.environ["LLM_PROVIDER"] = "mock"

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_mock_driver_echoes_input():
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app.llm.gateway import complete, Message

    response = await complete([
        Message(role="system", content="You are an analyst."),
        Message(role="user", content="Why is the ROP 18?"),
    ])
    assert "Mock LLM" in response
    assert "ROP" in response or "Why is" in response


@pytest.mark.asyncio
async def test_rationale_generator_uses_mock():
    from datetime import datetime, timezone, timedelta
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app.llm.rationale import generate_rationale
    from app.recommendations.models import (
        RecommendationDetail, Rationale, VendorInfo, FeatureContribution,
    )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rec = RecommendationDetail(
        rec_id="REC-LLM-001", item_id="PUMP-001",
        item_description="Centrifugal Pump", warehouse_id="BEDFORD",
        type="ROP", criticality="HIGH",
        current_value=32, recommended_value=18,
        delta_working_capital=11_440.0, confidence=0.92,
        status="NEW", version=1, created_at=now,
        wc_release=11_440.0, stock_out_risk_change_pct=-0.4,
        model_version="t", expires_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat().replace("+00:00", "Z"),
        rationale=Rationale(
            demand_pattern="intermittent", adi=1.7, cv_squared=0.6,
            twelve_month_mean_qty=84, lead_time_days_mean=14, lead_time_days_std=4,
            service_level_target=0.99, summary_text="original",
        ),
        feature_contributions=[
            FeatureContribution(name="lead_time", value=14, contribution=0.4),
        ],
        vendor=VendorInfo(
            vendor_id="V1", name="Acme",
            mean_lead_days=14, std_lead_days=4, on_time_pct=0.9,
            unit_cost=260, holding_cost_pct=0.22, order_cost=85,
        ),
        linked_assets=[], audit=[],
    )

    text = await generate_rationale(rec)
    assert text  # non-empty
    # Cached on second call
    text2 = await generate_rationale(rec)
    assert text == text2
