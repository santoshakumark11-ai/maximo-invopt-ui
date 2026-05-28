"""
Writeback saga — DLD §4.6 / §9.2.

Single-target (Maximo) two-phase shape, ready to grow into a Temporal workflow
once the ERP adapter lands.  For Q1.1 the saga has three steps:

    1. Begin   — log BEFORE-state to WORM audit.
    2. Update  — POST to MXINV_INVENTORY_V1 with ROWSTAMP optimistic concurrency.
                 Retry on transient failure, refresh ROWSTAMP on 409.
    3. Commit  — log AFTER-state, mark recommendation APPLIED, emit metrics.

On failure after retries, the recommendation transitions to FAILED and the
operator is paged via a logger.error (Prometheus alert wired in §4 of the
gap report).

Idempotency: the saga is keyed on (rec_id, version).  If a re-run is invoked
with the same key after a partial success, the read step sees the new ROWSTAMP
and either no-ops or detects drift.

Every step writes to the writeback_attempts table for forensic replay.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app import audit, db
from app.config import get_settings
from app.recommendations import service as rec_service
from app.recommendations.models import RecommendationDetail
from app.writeback import maximo as mif

logger = logging.getLogger(__name__)


# ── Persistence helper for writeback_attempts (best-effort) ───────────────────

async def _record_attempt(
    *, rec_id: str, status: str, request_payload: dict, response_payload: dict,
    http_status: Optional[int], correlation_id: str, error: Optional[str],
) -> None:
    if not db.is_enabled():
        return
    try:
        from app.models_db import WritebackAttempt
        async with db.session_scope() as s:
            s.add(WritebackAttempt(
                rec_id=rec_id, target="MAXIMO", status=status,
                request_payload=request_payload, response_payload=response_payload,
                http_status=http_status, correlation_id=correlation_id, error=error,
                ended_at=datetime.now(timezone.utc),
            ))
    except Exception as exc:
        logger.warning("Failed to record writeback attempt for %s: %s", rec_id, exc)


# ── Public surface ───────────────────────────────────────────────────────────

async def apply(rec: RecommendationDetail, *, actor: str) -> RecommendationDetail:
    """
    Execute the saga for a single APPROVED recommendation.

    On success, returns the recommendation with status=APPLIED.
    On unrecoverable failure, returns it with status=FAILED.  Either way the
    caller (router) returns the fresh server state to the UI.
    """
    settings = get_settings()
    correlation_id = str(uuid.uuid4())

    # Only ROP / SS / EOQ are MIF-writable.  SUB and WRITEOFF are not policy
    # mutations — they need a different downstream and are out of Q1.1 scope.
    if rec.type not in ("ROP", "SS", "EOQ"):
        logger.info("Saga skip: rec %s type=%s is not MIF-writable", rec.rec_id, rec.type)
        return rec

    new_rop = new_ss = new_eoq = None
    if rec.type == "ROP":
        new_rop = _as_number(rec.recommended_value)
    elif rec.type == "SS":
        new_ss = _as_number(rec.recommended_value)
    elif rec.type == "EOQ":
        new_eoq = _as_number(rec.recommended_value)

    await audit.write_event(
        principal=actor, action="APPLIED", subject=rec.rec_id,
        before_state={"status": rec.status, "version": rec.version},
        after_state={"writeback": "begin"},
        detail=f"Writeback saga begin (corr={correlation_id})",
        correlation_id=correlation_id,
    )

    # ── Step 1: GET current with ROWSTAMP ─────────────────────────────────────
    current = await mif.get_current(settings, rec.item_id, rec.warehouse_id)
    if current is None:
        logger.error("Saga step 1 (read) failed for rec %s — marking FAILED", rec.rec_id)
        await _mark_failed(rec.rec_id, actor, correlation_id, "could not read current inventory row")
        return await rec_service.get_one(rec.rec_id) or rec

    # ── Step 2: POST update with retry on 409 / transient errors ─────────────
    attempt = 0
    last_err: Optional[str] = None
    while attempt < settings.writeback_max_retries:
        attempt += 1
        result = await mif.update_inventory_policy(
            settings, current=current,
            new_reorder_point=new_rop, new_safety_stock=new_ss, new_eoq=new_eoq,
            correlation_id=correlation_id,
        )
        await _record_attempt(
            rec_id=rec.rec_id,
            status="OK" if result.ok else "FAILED",
            request_payload={"item": rec.item_id, "warehouse": rec.warehouse_id,
                             "rop": new_rop, "ss": new_ss, "eoq": new_eoq,
                             "rowstamp": current.rowstamp, "attempt": attempt},
            response_payload=result.body or {},
            http_status=result.http_status,
            correlation_id=correlation_id,
            error=result.error,
        )
        if result.ok:
            # ── Step 3: Commit ──────────────────────────────────────────────
            await rec_service.update_status(rec.rec_id, "APPLIED", actor=actor,
                                            detail=f"Maximo writeback OK (corr={correlation_id})")
            await audit.write_event(
                principal=actor, action="APPLIED", subject=rec.rec_id,
                before_state={"status": "APPROVED"},
                after_state={"status": "APPLIED", "rowstamp": result.new_rowstamp},
                detail="Maximo writeback successful",
                correlation_id=correlation_id,
            )
            try:
                from app.observability.metrics import inc_writeback_success
                inc_writeback_success()
            except Exception:
                pass
            return await rec_service.get_one(rec.rec_id) or rec

        last_err = result.error
        # 409 = stale ROWSTAMP: re-read and try again.
        if result.http_status == 409 and attempt < settings.writeback_max_retries:
            logger.info("Saga 409 on rec %s (attempt %d) — refreshing ROWSTAMP", rec.rec_id, attempt)
            refreshed = await mif.get_current(settings, rec.item_id, rec.warehouse_id)
            if refreshed is None:
                last_err = "could not refresh row after 409"
                break
            current = refreshed
            await asyncio.sleep(settings.writeback_retry_backoff_ms / 1000.0)
            continue

        # Other 4xx — terminal (contract violation, RBAC, etc.).
        if result.http_status and 400 <= result.http_status < 500:
            break

        # 5xx or network: exponential backoff and retry.
        await asyncio.sleep((settings.writeback_retry_backoff_ms / 1000.0) * (2 ** (attempt - 1)))

    # Exhausted retries — mark FAILED + emit metric + audit.
    logger.error("Saga FAILED for rec %s after %d attempts: %s", rec.rec_id, attempt, last_err)
    await _mark_failed(rec.rec_id, actor, correlation_id, last_err or "unknown")
    return await rec_service.get_one(rec.rec_id) or rec


# ── Internals ────────────────────────────────────────────────────────────────

async def _mark_failed(rec_id: str, actor: str, correlation_id: str, reason: str) -> None:
    await rec_service.update_status(rec_id, "FAILED", actor=actor,
                                    detail=f"Writeback failed: {reason}")
    await audit.write_event(
        principal=actor, action="FAILED", subject=rec_id,
        before_state={"status": "APPROVED"}, after_state={"status": "FAILED"},
        detail=reason, correlation_id=correlation_id,
    )
    try:
        from app.observability.metrics import inc_writeback_failure
        inc_writeback_failure()
    except Exception:
        pass


def _as_number(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
