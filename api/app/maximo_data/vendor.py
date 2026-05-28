"""
Vendor fetcher — v3 via INVVENDOR relationship on MXAPIINVENTORY.

The INVENTORY MBO carries a child relationship INVVENDOR with fields:
    VENDOR, ISDEFAULT, MANUFACTURER

These are already included in the oslc.select of our inventory pull (added in
Q1.2), so vendor data arrives in the same HTTP response as curbal, minlevel,
etc.  No separate API call required.

Selection logic:
    1. If an INVVENDOR row with isdefault=true exists → use that vendor.
    2. Else if any INVVENDOR rows exist → use the first one.
    3. Else → return None (generator falls back to _PLACEHOLDER_VENDOR).

For the vendor display name, we do a single MXAPICOMPANY lookup per distinct
vendor ID (cached).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import Settings
from app.recommendations.models import VendorInfo

logger = logging.getLogger(__name__)


def _headers(s: Settings) -> dict[str, str]:
    return {"apikey": s.maximo_api_key, "Accept": "application/json"}


def _get_val(row: dict, *keys: str) -> Any:
    for k in keys:
        for cand in (k, f"spi:{k}"):
            v = row.get(cand)
            if v is not None:
                return v
    return None


def _coerce_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# ── Company name cache ────────────────────────────────────────────────────────

_company_cache: dict[str, str] = {}


async def _company_name(vendor_id: str, settings: Settings) -> str:
    if vendor_id in _company_cache:
        return _company_cache[vendor_id]
    base = settings.maximo_base_url.rstrip("/")
    for os_name in ("MXAPICOMPANY", "MXAPICOMPANIES"):
        try:
            async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
                resp = await c.get(
                    f"{base}/api/os/{os_name}",
                    headers=_headers(settings),
                    params={
                        "oslc.select": "company,name",
                        "oslc.where":  f'company="{vendor_id}"',
                        "oslc.pageSize": "1",
                    },
                )
            if resp.is_success:
                data = resp.json()
                rows = data.get("member") or data.get("rdfs:member") or []
                if rows:
                    name = str(_get_val(rows[0], "name") or vendor_id)
                    _company_cache[vendor_id] = name
                    return name
        except Exception:
            continue
    _company_cache[vendor_id] = vendor_id
    return vendor_id


# ── Extract from inventory record's invvendor child ──────────────────────────

def _pick_vendor_from_inv(inv: dict[str, Any]) -> Optional[tuple[str, Optional[str]]]:
    """
    Returns (vendor_id, manufacturer) from the INVVENDOR child array, or None.
    Prefers the row with isdefault=true.
    """
    inv_vendors = _get_val(inv, "invvendor") or []
    if isinstance(inv_vendors, dict):
        inv_vendors = [inv_vendors]
    if not isinstance(inv_vendors, list) or not inv_vendors:
        return None

    # Pass 1: find the default vendor.
    for v in inv_vendors:
        if not isinstance(v, dict):
            continue
        is_default = _get_val(v, "isdefault")
        # isdefault can be True, 1, "true", "1"
        if is_default in (True, 1, "true", "1", "True"):
            vid = str(_get_val(v, "vendor") or "")
            mfr = str(_get_val(v, "manufacturer") or "")
            if vid:
                return (vid, mfr or None)

    # Pass 2: first row with a vendor ID.
    for v in inv_vendors:
        if not isinstance(v, dict):
            continue
        vid = str(_get_val(v, "vendor") or "")
        mfr = str(_get_val(v, "manufacturer") or "")
        if vid:
            return (vid, mfr or None)

    return None


# ── Public surface ────────────────────────────────────────────────────────────

async def fetch_vendor_blocks(
    inventory_records: list[dict[str, Any]],
    settings: Settings,
) -> dict[tuple[str, str], VendorInfo]:
    """
    Extracts vendor data from the INVVENDOR child relationship already present
    on the inventory records.  Returns dict[(item_id, warehouse_id), VendorInfo].

    No extra HTTP calls except one MXAPICOMPANY lookup per distinct vendor ID
    (to resolve the company display name).
    """
    _company_cache.clear()
    out: dict[tuple[str, str], VendorInfo] = {}

    for inv in inventory_records:
        itemnum = str(inv.get("itemnum") or inv.get("spi:itemnum") or "")
        siteid  = str(inv.get("siteid")  or inv.get("spi:siteid")  or "")
        if not itemnum or not siteid:
            continue
        # Q1 simplification: key by plain siteid to match the generator's lookup.
        warehouse_id = siteid

        result = _pick_vendor_from_inv(inv)
        if result is None:
            continue
        vendor_id, manufacturer = result

        # Get unit cost from INVCOST (already on the inventory record).
        raw_cost = _get_val(inv, "invcost") or {}
        if isinstance(raw_cost, list):
            raw_cost = raw_cost[0] if raw_cost else {}
        unit_cost = _coerce_float(
            _get_val(raw_cost, "avgcost") or _get_val(raw_cost, "stdcost")
        )

        # Resolve company display name (cached per vendor_id).
        name = await _company_name(vendor_id, settings)

        out[(itemnum, warehouse_id)] = VendorInfo(
            vendor_id=vendor_id,
            name=name,
            # Lead-time fields are merged in by the orchestrator from the
            # leadtime module's observations.  Defaults here are neutral.
            mean_lead_days=14.0,
            std_lead_days=4.0,
            on_time_pct=0.85,
            unit_cost=unit_cost,
            holding_cost_pct=0.20,
            order_cost=75.0,
        )

    logger.info("Vendor: resolved %d items from INVVENDOR child relationship", len(out))
    return out
