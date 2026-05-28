"""
WORM audit log — write & verify helpers.

Each row carries:
    prev_hash   — the row_hash of the previous audit row for the same subject
    row_hash    — HMAC-SHA256(prev_hash || canonical_json(row), audit_hmac_secret)

Verification walks the chain per subject and checks every row's HMAC.

This is intentionally simple — production-grade WORM should also stream the
chain to an external append-only store (S3 Object Lock, Db2 immutable rows,
Loki, etc.).  This module gives the cryptographic guarantee inside Postgres
which is enough for Q1 and forward-compatible with that streaming step.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings
from app import db

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import select, desc
    from app.models_db import AuditEvent
    _SA_OK = True
except Exception:
    _SA_OK = False


def _canonical(row: dict[str, Any]) -> str:
    """JSON with sorted keys + tight separators.  Hash-stable across runs."""
    return json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)


def _hmac(prev_hash: str, payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        (prev_hash + payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _ts_canonical(dt: datetime) -> str:
    """
    Render a timestamp in a form that is stable across SQLite roundtrips.

    SQLite has no native TIMESTAMP WITH TIMEZONE; SQLAlchemy strips tzinfo on
    read.  We also can't trust microsecond precision because the underlying
    driver may truncate.  So:
        - Normalise to UTC (adding tzinfo when missing).
        - Strip microseconds.
        - Emit as 'YYYY-MM-DDTHH:MM:SSZ'.

    The same function is applied on both write and verify paths, so the
    canonical payload that gets HMAC'd is byte-identical regardless of
    how the DB driver chose to store the column.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


async def write_event(
    *,
    principal: str,
    action: str,           # CREATED|EDITED|APPROVED|REJECTED|APPLIED|FAILED|VIEWED|NOTIFIED
    subject: str,          # rec_id
    before_state: Optional[dict[str, Any]] = None,
    after_state:  Optional[dict[str, Any]] = None,
    detail: Optional[str]  = None,
    tenant_id: str = "default",
    correlation_id: Optional[str] = None,
) -> Optional[str]:
    """
    Append one audit row.  Returns the new row_hash on success, None when
    persistence is disabled (the caller should treat that as best-effort).
    """
    if not (_SA_OK and db.is_enabled()):
        return None

    settings = get_settings()
    before_state = before_state or {}
    after_state  = after_state  or {}

    async with db.session_scope() as s:
        # Walk back to the previous row for this subject to compute prev_hash.
        stmt = (
            select(AuditEvent.row_hash)
            .where(AuditEvent.subject == subject)
            .order_by(desc(AuditEvent.event_id))
            .limit(1)
        )
        result = await s.execute(stmt)
        prev_hash = result.scalar() or ""

        ts = datetime.now(timezone.utc)
        canonical_payload = _canonical({
            "ts": _ts_canonical(ts),
            "tenant_id": tenant_id,
            "principal": principal,
            "action": action,
            "subject": subject,
            "before_state": before_state,
            "after_state": after_state,
            "detail": detail,
            "correlation_id": correlation_id,
        })
        row_hash = _hmac(prev_hash, canonical_payload, settings.audit_hmac_secret)

        # Strip microseconds before persistence so the stored ts matches what
        # _ts_canonical produced — keeps the chain consistent if anything ever
        # joins on row.ts directly.
        evt = AuditEvent(
            ts=ts.replace(microsecond=0),
            tenant_id=tenant_id,
            principal=principal,
            action=action,
            subject=subject,
            before_state=before_state,
            after_state=after_state,
            detail=detail,
            correlation_id=correlation_id,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        s.add(evt)

    return row_hash


async def verify_chain(subject: str) -> dict[str, Any]:
    """
    Walk the audit chain for `subject` and verify every row's HMAC.

    Returns:
        {
          "ok": bool,
          "rows_checked": int,
          "first_bad_event_id": int | None,
          "reason": str | None,
        }
    """
    if not (_SA_OK and db.is_enabled()):
        return {"ok": False, "rows_checked": 0, "first_bad_event_id": None,
                "reason": "persistence disabled"}

    settings = get_settings()

    async with db.session_scope() as s:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.subject == subject)
            .order_by(AuditEvent.event_id.asc())
        )
        result = await s.execute(stmt)
        rows = list(result.scalars().all())

    prev_hash = ""
    for row in rows:
        canonical_payload = _canonical({
            "ts": _ts_canonical(row.ts),
            "tenant_id": row.tenant_id,
            "principal": row.principal,
            "action": row.action,
            "subject": row.subject,
            "before_state": row.before_state,
            "after_state": row.after_state,
            "detail": row.detail,
            "correlation_id": row.correlation_id,
        })
        expected = _hmac(prev_hash, canonical_payload, settings.audit_hmac_secret)
        if expected != row.row_hash:
            return {
                "ok": False,
                "rows_checked": len(rows),
                "first_bad_event_id": row.event_id,
                "reason": "hmac mismatch",
            }
        if row.prev_hash != prev_hash:
            return {
                "ok": False,
                "rows_checked": len(rows),
                "first_bad_event_id": row.event_id,
                "reason": "prev_hash chain break",
            }
        prev_hash = row.row_hash

    return {"ok": True, "rows_checked": len(rows),
            "first_bad_event_id": None, "reason": None}
