"""
Maximo MIF client for the writeback path.

This is intentionally tiny — one read (current ROWSTAMP) and one write (POST
to the custom Object Structure MXINV_INVENTORY_V1 from DLD Appendix A).

Optimistic concurrency: every POST carries the ROWSTAMP returned by the
preceding GET; Maximo rejects with 409 when the stamp is stale.  The saga
catches the 409 and either retries or fails the recommendation (DLD §6.1).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CurrentInventory:
    """The fields we need before writing back."""
    itemnum: str
    siteid: str
    location: Optional[str]
    rowstamp: str
    reorderpoint: float
    safetystock: float
    economic_order_qty: float
    raw: dict[str, Any]


@dataclass
class WritebackResult:
    ok: bool
    http_status: Optional[int]
    body: Optional[dict[str, Any]]
    new_rowstamp: Optional[str]
    error: Optional[str]


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.maximo_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _resolve_url(settings: Settings, os_name: str) -> str:
    base = settings.maximo_base_url.rstrip("/")
    return f"{base}/api/os/{os_name}"


# ── Reads ─────────────────────────────────────────────────────────────────────

async def get_current(
    settings: Settings, item_id: str, warehouse_id: str,
) -> Optional[CurrentInventory]:
    """
    Look up the current inventory row to capture ROWSTAMP, current ROP/SS/EOQ,
    and confirm the storeroom binding.

    warehouse_id may be either 'SITEID' or 'SITEID/LOCATION'.
    """
    site, _, location = warehouse_id.partition("/")
    where = f'itemnum="{item_id}" and siteid="{site}"'
    if location:
        where += f' and location="{location}"'

    url = _resolve_url(settings, "MXAPIINVENTORY")
    params = {
        "oslc.select": "itemnum,siteid,location,rowstamp,minlevel,sstock,orderqty",
        "oslc.where":  where,
        "oslc.pageSize": "1",
    }

    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
            resp = await c.get(url, headers=_headers(settings), params=params)
    except httpx.RequestError as exc:
        logger.warning("MIF read failed for %s/%s: %s", item_id, warehouse_id, exc)
        return None

    if not resp.is_success:
        logger.warning("MIF read returned HTTP %s for %s/%s", resp.status_code, item_id, warehouse_id)
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    members = data.get("member") or data.get("rdfs:member") or []
    if not members:
        return None
    row = members[0]

    def _g(*keys: str, default: Any = None) -> Any:
        for k in keys:
            for cand in (k, f"spi:{k}"):
                v = row.get(cand)
                if v is not None:
                    return v
        return default

    return CurrentInventory(
        itemnum=_g("itemnum", default=item_id),
        siteid=_g("siteid", default=site),
        location=_g("location", default=location or None),
        rowstamp=str(_g("rowstamp", default="")),
        reorderpoint=float(_g("minlevel", "reorderpoint", default=0.0) or 0.0),
        safetystock=float(_g("sstock", "safetystock", default=0.0) or 0.0),
        economic_order_qty=float(_g("orderqty", "economicorderqty", default=0.0) or 0.0),
        raw=row,
    )


# ── Writes ────────────────────────────────────────────────────────────────────

async def update_inventory_policy(
    settings: Settings,
    *,
    current: CurrentInventory,
    new_reorder_point: Optional[float] = None,
    new_safety_stock:  Optional[float] = None,
    new_eoq:           Optional[float] = None,
    correlation_id: Optional[str] = None,
) -> WritebackResult:
    """
    POST update to MXINV_INVENTORY_V1.  Returns a structured result rather
    than raising — the saga reads `ok` and `http_status` to decide retry vs
    compensate vs fail-final.
    """
    url = _resolve_url(settings, settings.writeback_os_name)
    payload: dict[str, Any] = {
        "ITEMNUM": current.itemnum,
        "SITEID":  current.siteid,
        "ROWSTAMP": current.rowstamp,
    }
    if current.location:
        payload["LOCATION"] = current.location
    if new_reorder_point is not None:
        payload["MINLEVEL"] = new_reorder_point       # UI: "Reorder Point"
    if new_safety_stock is not None:
        payload["SSTOCK"] = new_safety_stock           # UI: "Safety Stock"
    if new_eoq is not None:
        payload["ORDERQTY"] = new_eoq                  # UI: "Economic Order Qty"

    headers = _headers(settings)
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id

    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
            resp = await c.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        return WritebackResult(ok=False, http_status=None, body=None,
                               new_rowstamp=None, error=f"network: {exc}")

    body: Optional[dict[str, Any]]
    try:
        body = resp.json() if resp.content else None
    except Exception:
        body = None

    if resp.is_success:
        new_rowstamp = None
        if body:
            new_rowstamp = body.get("rowstamp") or body.get("spi:rowstamp")
        return WritebackResult(ok=True, http_status=resp.status_code,
                               body=body, new_rowstamp=new_rowstamp, error=None)

    return WritebackResult(
        ok=False, http_status=resp.status_code, body=body,
        new_rowstamp=None,
        error=f"http {resp.status_code}: {resp.text[:200]}",
    )
