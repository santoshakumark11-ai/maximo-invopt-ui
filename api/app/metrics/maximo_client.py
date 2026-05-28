"""
Maximo REST API client for inventory data.

All queries use the service-account API key (apikey header).
No user credentials are transmitted here — only the backend service account
key stored in settings.

MXAPIINVENTORY object structure (relevant attributes):
  itemnum, siteid, curbal, reorderpoint, unitcost, status,
  orderunit, issue1y (issues last 12 months — used as demand proxy)
  item.description  — description lives on the related ITEM object

REST API select syntax:  ?oslc.select=itemnum,item.description,siteid,...
REST API where syntax:   ?oslc.where=siteid%3D%22BEDFORD%22
REST API pageSize:       ?oslc.pageSize=500

Response format:  {"member": [...], "totalCount": N}
  (Note: /api/os/ uses "member", NOT the OSLC "rdfs:member")
"""
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

# Max records to pull per query (Maximo REST API default is 100 if not specified)
_PAGE_SIZE = 500

# Attributes to select from MXAPIINVENTORY.
# - description is on the related ITEM object (item.description)
# - unit cost lives in the INVCOST relationship (avgcost / stdcost — no unitcost field)
# - reorderpoint and issue1y are direct fields but may be null/zero
# Q1.2: field names are the MBO attribute names from MXAPIINVENTORY, NOT the
# UI labels.  Key mappings (confirmed from the OS XML schema):
#   UI "Reorder Point"        → MINLEVEL
#   UI "Safety Stock"         → SSTOCK
#   UI "Economic Order Qty"   → ORDERQTY
#   UI "Lead Time (Days)"     → DELIVERYTIME
#   UI "Current Balance"      → via INVBALANCES.CURBAL (flattened by MAS)
_SELECT = ",".join([
    "itemnum",
    "item.description",
    "siteid",
    "location",
    "curbal",               # INVBALANCES child, flattened by MAS in JSON response
    "minlevel",             # = Reorder Point
    "sstock",               # = Safety Stock
    "orderqty",             # = Economic Order Quantity
    "deliverytime",         # = Lead Time in days
    "vendor",
    "status",
    "orderunit",
    "issue1yrago",          # issues last 12 months (ISSUE1YRAGO in the OS)
    "invcost.avgcost",
    "invcost.stdcost",
    "invvendor.vendor",
    "invvendor.isdefault",
    "invvendor.manufacturer",
])


def _api_url(settings: Settings) -> str:
    base = settings.maximo_base_url.rstrip("/")
    return f"{base}/api/os/MXAPIINVENTORY"


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.maximo_api_key,
        "Accept": "application/json",
    }


async def fetch_inventory(settings: Settings) -> list[dict[str, Any]]:
    """
    Pull all MXAPIINVENTORY records (up to _PAGE_SIZE) and return raw dicts.
    Falls back to an empty list if Maximo is unavailable.

    No oslc.where filter is applied here — status filtering varies by site and
    Maximo version.  Compute functions downstream ignore zero-balance records
    where appropriate.
    """
    url = _api_url(settings)
    params = {
        "oslc.select": _SELECT,
        "oslc.pageSize": str(_PAGE_SIZE),
    }

    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as client:
            resp = await client.get(url, headers=_headers(settings), params=params)
    except httpx.RequestError as exc:
        logger.warning("MXAPIINVENTORY request failed: %s", exc)
        return []

    if not resp.is_success:
        logger.warning("MXAPIINVENTORY returned HTTP %s — body: %s",
                       resp.status_code, resp.text[:200])
        return []

    try:
        data = resp.json()
    except Exception:
        logger.warning("MXAPIINVENTORY response is not JSON")
        return []

    # Log top-level keys to help diagnose unexpected response shapes
    logger.debug("MXAPIINVENTORY response keys: %s", list(data.keys()))

    # /api/os/ wraps records under "member"; some MAS versions still use "rdfs:member"
    members: list[dict[str, Any]] = (
        data.get("member")
        or data.get("rdfs:member")
        or []
    )
    logger.info(
        "Fetched %d MXAPIINVENTORY records (totalCount=%s)",
        len(members),
        data.get("totalCount", "?"),
    )
    if members:
        first = members[0]
        logger.debug("MXAPIINVENTORY first record keys: %s", list(first.keys()))
    return members


# ── Helpers to normalise REST API attribute names ─────────────────────────────

def _get(rec: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Try multiple key spellings (MAS prefixes scalar fields with 'spi:').

    IMPORTANT: uses explicit `is not None` — NOT `or` — so that legitimate
    zero / 0.0 values are returned rather than falling through to the default.
    """
    for k in keys:
        for candidate in (k, f"spi:{k}"):
            v = rec.get(candidate)
            if v is not None:
                return v
    return default


def _get_description(rec: dict[str, Any]) -> str:
    """
    Extract item description from the nested ITEM relationship.

    oslc.select 'item.description' returns:
      { "item": { "description": "Some desc" } }
    Confirmed from live logs: key is plain "item", value is plain dict.
    """
    item_obj = rec.get("item") or rec.get("spi:item") or {}
    return str(item_obj.get("description") or item_obj.get("spi:description") or "")


def _get_unitcost(rec: dict[str, Any]) -> float:
    """
    Extract unit cost from the INVCOST relationship.

    INVCOST has avgcost and stdcost — no 'unitcost' field in this object structure.
    Prefer avgcost; fall back to stdcost.

    oslc.select 'invcost.avgcost' returns a list (INVCOST is a child table):
      { "invcost": [ { "avgcost": 12.50, "stdcost": 11.80 }, ... ] }
    or a single dict on some MAS versions.
    """
    raw = rec.get("invcost") or rec.get("spi:invcost")
    if not raw:
        return 0.0
    # Normalise — could be a list or a single dict
    entry: dict[str, Any] = raw[0] if isinstance(raw, list) else raw
    for key in ("avgcost", "spi:avgcost", "stdcost", "spi:stdcost"):
        v = entry.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


def _float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Derived KPI calculations ──────────────────────────────────────────────────

def compute_kpi_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_items = len(records)
    total_value = 0.0
    below_reorder = 0
    stockout_risk = 0
    excess_stock = 0

    for r in records:
        curbal = _float(_get(r, "curbal"))
        reorder = _float(_get(r, "minlevel", "reorderpoint"))
        unitcost = _get_unitcost(r)
        issue1y = _float(_get(r, "issue1yrago", "issue1y"))

        total_value += curbal * unitcost

        if curbal <= 0:
            stockout_risk += 1
        elif reorder > 0 and curbal < reorder:
            below_reorder += 1

        # Excess: balance > 2× annual usage (simple heuristic)
        if issue1y > 0 and curbal > 2 * issue1y:
            excess_stock += 1

    return {
        "total_items": total_items,
        "total_value": round(total_value, 2),
        "below_reorder": below_reorder,
        "stockout_risk": stockout_risk,
        "excess_stock": excess_stock,
    }


def compute_inventory_by_status(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {
        "OK":            {"status": "OK",            "count": 0, "value": 0.0},
        "Below Reorder": {"status": "Below Reorder", "count": 0, "value": 0.0},
        "Stockout Risk": {"status": "Stockout Risk", "count": 0, "value": 0.0},
        "Excess":        {"status": "Excess",        "count": 0, "value": 0.0},
    }

    for r in records:
        curbal = _float(_get(r, "curbal"))
        reorder = _float(_get(r, "minlevel", "reorderpoint"))
        unitcost = _get_unitcost(r)
        issue1y = _float(_get(r, "issue1yrago", "issue1y"))
        value = curbal * unitcost

        if curbal <= 0:
            key = "Stockout Risk"
        elif reorder > 0 and curbal < reorder:
            key = "Below Reorder"
        elif issue1y > 0 and curbal > 2 * issue1y:
            key = "Excess"
        else:
            key = "OK"

        buckets[key]["count"] += 1
        buckets[key]["value"] = round(buckets[key]["value"] + value, 2)

    return list(buckets.values())


def compute_top_items_by_risk(
    records: list[dict[str, Any]], limit: int = 20
) -> list[dict[str, Any]]:
    """
    Return top items ranked by working-capital release potential.

    Scoring strategy (applied in priority order):
    1. Reorder point configured + item is BELOW reorder → stockout risk score
       (gap / reorder * 50 + log10(annual_value+1) * 10)
    2. Reorder point configured + item is ABOVE reorder → excess stock score
       (excess_value / total_value * 100)
    3. No reorder point → fall back to ranking by total inventory value so the
       table always shows something useful when reorder points aren't set up.
    """
    import math

    items = []
    for r in records:
        curbal   = _float(_get(r, "curbal"))
        reorder  = _float(_get(r, "minlevel", "reorderpoint"))
        unitcost = _get_unitcost(r)
        issue1y  = _float(_get(r, "issue1yrago", "issue1y"))

        # Skip items with no balance and no cost — nothing meaningful to show
        inv_value = curbal * unitcost
        if curbal <= 0 and unitcost <= 0:
            continue

        if reorder > 0:
            gap = reorder - curbal  # positive = below reorder (risk)
            if gap > 0:
                # Below reorder: score by how critical the shortfall is
                annual_value = issue1y * unitcost
                score = min(100.0,
                    (gap / reorder) * 50 + math.log10(annual_value + 1) * 10)
            else:
                # Above reorder: score by excess value as % of total value
                excess_value = abs(gap) * unitcost
                score = min(50.0, math.log10(excess_value + 1) * 8)
        else:
            # No reorder point — score purely by inventory value
            score = min(30.0, math.log10(inv_value + 1) * 6) if inv_value > 0 else 0.0

        items.append({
            "item_num":      str(_get(r, "itemnum") or ""),
            "description":   _get_description(r),
            "site_id":       str(_get(r, "siteid") or ""),
            "current_bal":   round(curbal, 2),
            "reorder_point": round(reorder, 2),
            "unit_cost":     round(unitcost, 2),
            "risk_score":    round(score, 1),
        })

    items.sort(key=lambda x: x["risk_score"], reverse=True)
    return items[:limit]
