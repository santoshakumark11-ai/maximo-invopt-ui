"""
Agent executor — reads NEW recs, evaluates policy, auto-applies qualifying ones.

Called by:
    - POST /v1/agent:run (on demand)
    - orchestration.nightly.run_batch (after recommendation generation)
    - scheduler (if wired)

Every auto-apply goes through the SAME writeback saga as a planner approval,
so every action lands in the WORM audit log with principal="agent".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.agent.policy import evaluate, PolicyDecision
from app.recommendations import service as rec_service
from app.recommendations.models import RecommendationDetail

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    evaluated: int
    auto_approved: int
    auto_applied: int
    skipped: int
    failed: int
    decisions: list[dict[str, Any]]


def _get_val(row: dict, *keys: str) -> Any:
    for k in keys:
        for cand in (k, f"spi:{k}"):
            v = row.get(cand)
            if v is not None:
                return v
    return None


async def _open_po_qty(item_id: str, site_id: str, settings: Settings) -> float:
    """
    Query MXAPIPO for open PO lines for this item.  Sum the ordered-but-
    not-yet-received quantity.
    """
    base = settings.maximo_base_url.rstrip("/")
    url = f"{base}/api/os/MXAPIPO"
    params = {
        "oslc.select": "poline.itemnum,poline.orderqty,poline.receivedqty",
        "oslc.where": (
            f'poline.itemnum="{item_id}" and siteid="{site_id}" '
            f'and status in ["APPR","INPRG"]'
        ),
        "oslc.pageSize": "50",
    }
    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
            headers = {"apikey": settings.maximo_api_key, "Accept": "application/json"}
            resp = await c.get(url, headers=headers, params=params)
        if not resp.is_success:
            return 0.0
        data = resp.json()
        rows = data.get("member") or data.get("rdfs:member") or []
    except Exception:
        return 0.0

    total_open = 0.0
    for po in rows:
        polines = _get_val(po, "poline") or []
        if isinstance(polines, dict):
            polines = [polines]
        for pl in polines:
            pl_item = str(_get_val(pl, "itemnum") or "")
            if pl_item.upper() != item_id.upper():
                continue
            ordered  = float(_get_val(pl, "orderqty")    or 0)
            received = float(_get_val(pl, "receivedqty") or 0)
            total_open += max(0.0, ordered - received)
    return total_open


async def run(*, settings: Optional[Settings] = None) -> AgentRunResult:
    """
    Evaluate all NEW recommendations against the auto-apply policy.
    """
    settings = settings or get_settings()

    if not settings.agent_auto_apply_enabled:
        return AgentRunResult(
            evaluated=0, auto_approved=0, auto_applied=0, skipped=0, failed=0,
            decisions=[{"note": "agent disabled by settings"}],
        )

    all_recs = await rec_service.list_all()
    new_recs = [r for r in all_recs if r.status == "NEW"]

    result = AgentRunResult(
        evaluated=len(new_recs), auto_approved=0, auto_applied=0,
        skipped=0, failed=0, decisions=[],
    )

    for rec in new_recs:
        # Cross-check open POs.
        site_id = rec.warehouse_id.split("/")[0] if "/" in rec.warehouse_id else rec.warehouse_id
        open_qty = await _open_po_qty(rec.item_id, site_id, settings)

        decision = evaluate(rec, open_po_qty=open_qty)
        entry = {
            "recId": rec.rec_id,
            "itemId": rec.item_id,
            "criticality": rec.criticality,
            "deltaWc": rec.delta_working_capital,
            "openPoQty": open_qty,
            "approved": decision.approved,
            "reason": decision.reason,
        }

        if not decision.approved:
            result.skipped += 1
            result.decisions.append(entry)
            continue

        # Auto-approve → writeback saga.
        result.auto_approved += 1
        try:
            updated = await rec_service.update_status(
                rec.rec_id, "APPROVED", actor="agent",
                detail=f"Auto-approved by agent: {decision.reason}",
            )
            if updated and settings.writeback_enabled:
                try:
                    from app.writeback import saga
                    await saga.apply(updated, actor="agent")
                    result.auto_applied += 1
                except Exception as exc:
                    logger.warning("Agent writeback failed for %s: %s", rec.rec_id, exc)
                    result.failed += 1
            else:
                result.auto_applied += 1  # approved but writeback is off
        except Exception as exc:
            logger.warning("Agent approve failed for %s: %s", rec.rec_id, exc)
            result.failed += 1

        result.decisions.append(entry)

    logger.info(
        "Agent run: %d evaluated, %d auto-approved, %d applied, %d skipped, %d failed",
        result.evaluated, result.auto_approved, result.auto_applied,
        result.skipped, result.failed,
    )
    return result
