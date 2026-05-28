"""
Unit tests for the WORM audit hash chain.
Uses the in-memory SQLite URL configured in conftest.py.
"""
import os
import pytest

# Enable persistence for this module only — conftest defaults to off.
os.environ["PERSISTENCE_ENABLED"] = "true"

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_audit_chain_is_consistent():
    """Walk the chain forward and verify every row's HMAC."""
    # Late imports so the env override above takes effect.
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import audit, db
    await db.init_db()

    rec_id = "REC-TEST-0001"
    await audit.write_event(principal="alice", action="CREATED", subject=rec_id)
    await audit.write_event(principal="alice", action="VIEWED",  subject=rec_id)
    await audit.write_event(principal="bob",   action="APPROVED", subject=rec_id,
                            detail="LGTM")
    res = await audit.verify_chain(rec_id)
    assert res["ok"] is True
    assert res["rows_checked"] == 3


@pytest.mark.asyncio
async def test_audit_chain_detects_tampering():
    """If a row's after_state is mutated post-write, verify_chain reports the break."""
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import audit, db
    from app.models_db import AuditEvent
    from sqlalchemy import select

    await db.init_db()
    rec_id = "REC-TEST-0002"
    await audit.write_event(principal="alice", action="CREATED", subject=rec_id)
    await audit.write_event(principal="alice", action="APPROVED", subject=rec_id,
                            after_state={"status": "APPROVED"})

    # Tamper with the SECOND row without re-signing.
    async with db.session_scope() as s:
        rows = (await s.execute(
            select(AuditEvent).where(AuditEvent.subject == rec_id)
            .order_by(AuditEvent.event_id.asc())
        )).scalars().all()
        rows[1].after_state = {"status": "REJECTED"}

    res = await audit.verify_chain(rec_id)
    assert res["ok"] is False
    assert res["reason"] in ("hmac mismatch", "prev_hash chain break")
