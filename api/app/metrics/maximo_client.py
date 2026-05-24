"""
Maximo OSLC client for inventory data.

All queries use the service-account API key (passed as apikey query parameter
or as the maxauth header, depending on MAS version).  No user credentials are
transmitted here — only the backend service account key stored in settings.

MXINVENTORY object structure (relevant attributes):
  itemnum, description, siteid, curbal, reorderpoint, unitcost, status,
  orderunit, issue1y (issues last 12 months — used as demand proxy)

OSLC select syntax:  ?oslc.select=itemnum,description,siteid,...
OSLC where syntax:   ?oslc.where=siteid%3D%22BEDFORD%22
OSLC pageSize:       ?oslc.pageSize=500
"""
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

# Max records to pull per query (Maximo OSLC default is 100 if not specified)
_PAGE_SIZE = 500

# OSLC attributes we need from MXINVENTORY
_SELECT = ",".join([
    "itemnum",
    "description",
    "siteid",
    "curbal",
    "reorderpoint",
    "unitcost",
    "status",
    "orderunit",
    "issue1y",
    "avginvcost",
])


def _api_url(settings: Settings) -> str:
    base = settings.maximo_base_url.rstrip("/")
    return f"{base}/oslc/os/mxinventory"


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.maximo_api_key,
        "Accept": "application/json",
    }


async def fetch_inventory(settings: Settings) -> list[dict[str, Any]]:
    """
    Pull all MXINVENTORY records (up to _PAGE_SIZE) and return raw dicts.
    Falls back to an empty list if Maximo is unavailable.
    """
    url = _api_url(settings)
    params = {
        "oslc.select": _SELECT,
        "oslc.pageSize": str(_PAGE_SIZE),
        # Only active / storeroom inventory
        "oslc.where": "status=\"ACTIVE\"",
    }

    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as client:
            resp = await client.get(url, headers=_headers(settings), params=params)
    except httpx.RequestError as exc:
        logger.warning("MXINVENTORY request failed: %s", exc)
        return []

    if not resp.is_success:
        logger.warning("MXINVENTORY returned HTTP %s", resp.status_code)
        return []

    try:
        data = resp.json()
    except Exception:
        logger.warning("MXINVENTORY response is not JSON")
        return []

    # OSLC wraps records under rdfs:member
    members: list[dict[str, Any]] = data.get("rdfs:member", [])
    logger.info("Fetched %d MXINVENTORY records", len(members))
    return members


# ── Helpers to normalise OSLC attribute names ─────────────────────────────────

def _get(rec: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Try multiple key spellings (MAS sometimes prefixes with 'spi:')."""
    for k in keys:
        v = rec.get(k) or rec.get(f"spi:{k}")
        if v is not None:
            return v
    return default


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
        curbal = _float(_get(r, "curbal", "CURBAL"))
        reorder = _float(_get(r, "reorderpoint", "REORDERPOINT"))
        unitcost = _float(_get(r, "unitcost", "UNITCOST"))
        issue1y = _float(_get(r, "issue1y", "ISSUE1Y"))

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
        curbal = _float(_get(r, "curbal", "CURBAL"))
        reorder = _float(_get(r, "reorderpoint", "REORDERPOINT"))
        unitcost = _float(_get(r, "unitcost", "UNITCOST"))
        issue1y = _float(_get(r, "issue1y", "ISSUE1Y"))
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
    items = []
    for r in records:
        curbal = _float(_get(r, "curbal", "CURBAL"))
        reorder = _float(_get(r, "reorderpoint", "REORDERPOINT"))
        unitcost = _float(_get(r, "unitcost", "UNITCOST"))
        issue1y = _float(_get(r, "issue1y", "ISSUE1Y"))

        if reorder <= 0:
            continue  # can't calculate risk without a reorder point

        # Risk score: how far below reorder, weighted by annual usage value
        gap = reorder - curbal
        if gap <= 0:
            continue  # not below reorder

        annual_value = issue1y * unitcost
        # Normalise: score = gap/reorder * 50 + log10(annual_value+1) * 10
        import math
        score = min(100.0, (gap / reorder) * 50 + math.log10(annual_value + 1) * 10)

        items.append({
            "item_num":     str(_get(r, "itemnum", "ITEMNUM", default="")),
            "description":  str(_get(r, "description", "DESCRIPTION", default="")),
            "site_id":      str(_get(r, "siteid", "SITEID", default="")),
            "current_bal":  round(curbal, 2),
            "reorder_point": round(reorder, 2),
            "unit_cost":    round(unitcost, 2),
            "risk_score":   round(score, 1),
        })

    items.sort(key=lambda x: x["risk_score"], reverse=True)
    return items[:limit]
