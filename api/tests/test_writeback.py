"""
Saga test — mocks httpx so no real Maximo is needed.

Scenarios:
    - First POST returns 200 → recommendation transitions to APPLIED.
    - First POST returns 409 (stale ROWSTAMP) → saga refreshes and retries; succeeds.
    - All retries fail → recommendation transitions to FAILED.
"""
import os
import pytest

os.environ["PERSISTENCE_ENABLED"] = "true"
os.environ["WRITEBACK_ENABLED"]   = "true"

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_saga_success(monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import db
    from app.recommendations import service as rec_service
    from app.recommendations.models import (
        RecommendationDetail, Rationale, VendorInfo,
    )
    from app.writeback import saga, maximo as mif

    await db.init_db()

    rec = _make_rec("REC-SAGA-OK", rop_target=18.0)
    # Seed directly into the DB via the service (it forwards to repo when DB on).
    from app.recommendations import repo
    await repo.replace_all([rec])

    async def fake_get_current(*a, **kw):
        return mif.CurrentInventory(
            itemnum=rec.item_id, siteid=rec.warehouse_id, location=None,
            rowstamp="STAMP-1", reorderpoint=32.0, safetystock=0.0,
            economic_order_qty=0.0, raw={},
        )

    async def fake_update(*a, **kw):
        return mif.WritebackResult(
            ok=True, http_status=200, body={"rowstamp": "STAMP-2"},
            new_rowstamp="STAMP-2", error=None,
        )

    monkeypatch.setattr(mif, "get_current",            fake_get_current)
    monkeypatch.setattr(mif, "update_inventory_policy", fake_update)

    result = await saga.apply(rec, actor="alice")
    assert result.status == "APPLIED"


@pytest.mark.asyncio
async def test_saga_retries_on_409(monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import db
    from app.recommendations import repo
    from app.writeback import saga, maximo as mif

    await db.init_db()
    rec = _make_rec("REC-SAGA-409", rop_target=18.0)
    await repo.replace_all([rec])

    state = {"calls": 0}

    async def fake_get_current(*a, **kw):
        state["calls"] += 1
        # Hand out a fresh ROWSTAMP each refresh so the saga's "refreshed"
        # branch can be observed.
        return mif.CurrentInventory(
            itemnum=rec.item_id, siteid=rec.warehouse_id, location=None,
            rowstamp=f"STAMP-{state['calls']}", reorderpoint=32.0,
            safetystock=0.0, economic_order_qty=0.0, raw={},
        )

    posts: list[dict] = []

    async def fake_update(settings, *, current, new_reorder_point, **kw):
        posts.append({"rowstamp": current.rowstamp})
        if len(posts) == 1:
            return mif.WritebackResult(ok=False, http_status=409, body={},
                                       new_rowstamp=None, error="stale rowstamp")
        return mif.WritebackResult(ok=True, http_status=200, body={"rowstamp": "OK"},
                                   new_rowstamp="OK", error=None)

    monkeypatch.setattr(mif, "get_current",            fake_get_current)
    monkeypatch.setattr(mif, "update_inventory_policy", fake_update)

    result = await saga.apply(rec, actor="alice")
    assert result.status == "APPLIED"
    assert len(posts) == 2
    assert posts[0]["rowstamp"] != posts[1]["rowstamp"]


@pytest.mark.asyncio
async def test_saga_marks_failed_after_exhausting_retries(monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import db
    from app.recommendations import repo
    from app.writeback import saga, maximo as mif

    await db.init_db()
    rec = _make_rec("REC-SAGA-FAIL", rop_target=18.0)
    await repo.replace_all([rec])

    async def fake_get_current(*a, **kw):
        return mif.CurrentInventory(
            itemnum=rec.item_id, siteid=rec.warehouse_id, location=None,
            rowstamp="STAMP-X", reorderpoint=32.0, safetystock=0.0,
            economic_order_qty=0.0, raw={},
        )

    async def fake_update(*a, **kw):
        return mif.WritebackResult(ok=False, http_status=500, body={},
                                   new_rowstamp=None, error="server error")

    monkeypatch.setattr(mif, "get_current",            fake_get_current)
    monkeypatch.setattr(mif, "update_inventory_policy", fake_update)

    result = await saga.apply(rec, actor="alice")
    assert result.status == "FAILED"


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_rec(rec_id: str, *, rop_target: float):
    from datetime import datetime, timezone, timedelta
    from app.recommendations.models import (
        RecommendationDetail, Rationale, VendorInfo,
    )
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return RecommendationDetail(
        rec_id=rec_id, item_id="P-1042",
        item_description="Pump", warehouse_id="BEDFORD",
        type="ROP", criticality="HIGH",
        current_value=32, recommended_value=rop_target,
        delta_working_capital=11_440.0, confidence=0.92,
        status="APPROVED", version=1, created_at=now,
        wc_release=11_440.0, stock_out_risk_change_pct=-0.4,
        model_version="t", expires_at=(datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat().replace("+00:00", "Z"),
        rationale=Rationale(
            demand_pattern="intermittent", adi=1.7, cv_squared=0.6,
            twelve_month_mean_qty=84, lead_time_days_mean=14, lead_time_days_std=4,
            service_level_target=0.99, summary_text="test",
        ),
        feature_contributions=[], vendor=VendorInfo(
            vendor_id="V1", name="Acme",
            mean_lead_days=14, std_lead_days=4, on_time_pct=0.9,
            unit_cost=260, holding_cost_pct=0.22, order_cost=85,
        ),
        linked_assets=[], audit=[],
    )
