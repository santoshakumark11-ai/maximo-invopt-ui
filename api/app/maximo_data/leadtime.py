"""
Lead-time observations — v3 via matrectrans_collectionref.

The MXAPIINVENTORY OS schema shows MATRECTRANS as a child relationship
(filter=true), which means each inventory record carries a
`matrectrans_collectionref` URL — exactly the same pattern the demand
fetcher uses for `matusetrans_collectionref`.

Approach per item:
  1. Follow `matrectrans_collectionref` on the inventory record.
  2. For each receipt row, extract PONUM + ACTUALDATE.
  3. For each distinct PONUM, look up MXAPIPO to get orderdate.
  4. lead_time_days = max(1, (receipt.actualdate - po.orderdate)).
  5. Return dict[(itemnum, warehouse_id), list[lead_time_days]].

Falls back to a direct MXAPIPO query per item if the collection ref is absent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_PAGE_SIZE = 500


def _headers(s: Settings) -> dict[str, str]:
    return {"apikey": s.maximo_api_key, "Accept": "application/json"}


async def _get_members(url: str, settings: Settings,
                       params: dict | None = None) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
            resp = await c.get(url, headers=_headers(settings), params=params or {})
    except httpx.RequestError as exc:
        logger.debug("Lead-time HTTP error for %s: %s", url, exc)
        return []
    if not resp.is_success:
        logger.debug("Lead-time HTTP %s for %s", resp.status_code, url)
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    return data.get("member") or data.get("rdfs:member") or []


def _parse_iso(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _get_val(row: dict, *keys: str) -> Any:
    for k in keys:
        for cand in (k, f"spi:{k}"):
            v = row.get(cand)
            if v is not None:
                return v
    return None


# ── PO order-date cache (cleared per batch run) ─────────────────────────────

_po_cache: dict[str, Optional[datetime]] = {}


async def _orderdate_for_po(po_num: str, settings: Settings) -> Optional[datetime]:
    if po_num in _po_cache:
        return _po_cache[po_num]
    base = settings.maximo_base_url.rstrip("/")
    url = f"{base}/api/os/MXAPIPO"
    params = {
        "oslc.select":   "ponum,orderdate,statusdate",
        "oslc.where":    f'ponum="{po_num}"',
        "oslc.pageSize": "1",
    }
    rows = await _get_members(url, settings, params)
    if not rows:
        _po_cache[po_num] = None
        return None
    row = rows[0]
    dt = _parse_iso(_get_val(row, "orderdate") or _get_val(row, "statusdate"))
    _po_cache[po_num] = dt
    return dt


# ── Public surface ───────────────────────────────────────────────────────────

async def fetch_lead_times(
    inventory_records: list[dict[str, Any]],
    settings: Settings,
    *,
    history_months: int = 24,
) -> dict[tuple[str, str], list[float]]:
    """
    Per-item lead-time observations via matrectrans_collectionref.
    Returns dict[(item_id, warehouse_id), list[lead_time_days]].
    """
    _po_cache.clear()
    out: dict[tuple[str, str], list[float]] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=history_months * 30)

    seen: set[tuple[str, str]] = set()
    for inv in inventory_records:
        itemnum = str(inv.get("itemnum") or inv.get("spi:itemnum") or "")
        siteid  = str(inv.get("siteid")  or inv.get("spi:siteid")  or "")
        if not itemnum or not siteid:
            continue

        key_pair = (itemnum, siteid)
        if key_pair in seen:
            continue
        seen.add(key_pair)

        # Q1 simplification: key by plain siteid to match the generator's lookup.
        warehouse_id = siteid

        # ── Strategy 1: follow matrectrans_collectionref ─────────────────
        coll_ref = (
            inv.get("matrectrans_collectionref")
            or inv.get("spi:matrectrans_collectionref")
        )
        receipt_rows: list[dict[str, Any]] = []
        if coll_ref:
            params = {
                "oslc.select": "actualdate,ponum,quantity",
                "oslc.pageSize": str(_PAGE_SIZE),
            }
            receipt_rows = await _get_members(coll_ref, settings, params)

        # ── Strategy 2: direct MXAPIPO query ─────────────────────────────
        if not receipt_rows:
            base = settings.maximo_base_url.rstrip("/")
            url = f"{base}/api/os/MXAPIPO"
            params = {
                "oslc.select": "ponum,orderdate,statusdate",
                "oslc.where":  f'poline.itemnum="{itemnum}" and siteid="{siteid}"',
                "oslc.pageSize": str(_PAGE_SIZE),
            }
            po_rows = await _get_members(url, settings, params)
            # From PO rows we can compute lead time as (today or statusdate) - orderdate
            # when there's no MATRECTRANS receipt to pair with.
            for row in po_rows:
                order_dt = _parse_iso(_get_val(row, "orderdate"))
                status_dt = _parse_iso(_get_val(row, "statusdate"))
                if order_dt and status_dt and status_dt > cutoff:
                    d = max(1.0, (status_dt - order_dt).total_seconds() / 86400.0)
                    if d <= 365:
                        out.setdefault((itemnum, warehouse_id), []).append(d)
            continue

        # ── Process MATRECTRANS receipts ─────────────────────────────────
        days_list: list[float] = []
        for row in receipt_rows:
            receipt_dt = _parse_iso(_get_val(row, "actualdate"))
            if not receipt_dt or receipt_dt < cutoff:
                continue
            po_num = str(_get_val(row, "ponum") or "")
            if not po_num:
                continue
            order_dt = await _orderdate_for_po(po_num, settings)
            if order_dt is None:
                continue
            d = max(1.0, (receipt_dt - order_dt).total_seconds() / 86400.0)
            if d <= 365:
                days_list.append(d)

        if days_list:
            out[(itemnum, warehouse_id)] = days_list

    logger.info(
        "Fetched %d lead-time observations across %d items",
        sum(len(v) for v in out.values()), len(out),
    )
    return out
