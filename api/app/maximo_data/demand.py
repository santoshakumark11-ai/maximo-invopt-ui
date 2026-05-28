"""
MATUSETRANS demand history fetcher.

For each inventory record we:
  1. Follow the matusetrans_collectionref URL (if present in the inventory
     payload), or, if absent, construct the OSLC query directly against
     MXAPIINVENTORY with the item+site filter.
  2. Select actualdate, quantity, transtype, and aggregate ISSUE transactions
     into monthly buckets for the last N months (default 24).
  3. Return a vector ordered oldest → newest, padded with zeros for months
     with no issues.

The aggregation is intentionally per-(item, site) — multi-storeroom items
need separate vectors, which the orchestrator handles by keying the dict on
the warehouse_id used in the recommendation entity.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
_TRANSTYPE_ISSUE = {"ISSUE", "TRANSFER", "RETURN"}  # treat returns as demand reversal


def _headers(s: Settings) -> dict[str, str]:
    return {"apikey": s.maximo_api_key, "Accept": "application/json"}


def _coerce_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _yyyymm(dt: datetime | date) -> str:
    return dt.strftime("%Y-%m")


def _months_back(now: datetime, n: int) -> list[str]:
    """Return last-n YYYY-MM strings, oldest first."""
    out: list[str] = []
    cur = now.replace(day=1)
    for _ in range(n):
        out.append(_yyyymm(cur))
        prev_month_end = cur - timedelta(days=1)
        cur = prev_month_end.replace(day=1)
    out.reverse()
    return out


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get_json(url: str, settings: Settings, params: dict | None = None) -> dict | None:
    try:
        async with httpx.AsyncClient(verify=False, timeout=settings.maximo_timeout) as c:
            resp = await c.get(url, headers=_headers(settings), params=params or {})
    except httpx.RequestError as exc:
        logger.warning("MATUSETRANS fetch failed for %s: %s", url, exc)
        return None
    if not resp.is_success:
        logger.warning("MATUSETRANS HTTP %s for %s", resp.status_code, url)
        return None
    try:
        return resp.json()
    except Exception:
        return None


# ── Aggregator ────────────────────────────────────────────────────────────────

def _aggregate_monthly(rows: list[dict[str, Any]], months: list[str]) -> list[float]:
    bucket: dict[str, float] = defaultdict(float)
    for r in rows:
        ttype = (r.get("transtype") or r.get("spi:transtype") or "").upper()
        if ttype not in _TRANSTYPE_ISSUE:
            continue
        qty = _coerce_float(r.get("quantity") or r.get("spi:quantity"))
        if qty == 0:
            continue
        # Return / reversal transactions reduce demand.
        signed_qty = qty if ttype == "ISSUE" else (-qty if ttype == "RETURN" else qty)
        d = r.get("actualdate") or r.get("spi:actualdate")
        if not d:
            continue
        try:
            dt = datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        except Exception:
            continue
        bucket[_yyyymm(dt)] += signed_qty

    return [max(0.0, bucket.get(m, 0.0)) for m in months]


# ── Public surface ────────────────────────────────────────────────────────────

async def fetch_demand_for_inventory_records(
    inventory_records: list[dict[str, Any]],
    settings: Settings,
    *,
    history_months: int = 24,
) -> dict[tuple[str, str], list[float]]:
    """
    For each (itemnum, siteid) in the inventory pull, fetch MATUSETRANS history
    and return a dict keyed by (item_id, warehouse_id) → monthly demand vector.

    Note: warehouse_id is the storeroom siteid (or 'SITE/LOCATION' if location
    is present on the inventory row) — must match the value persisted on the
    Recommendation entity so the orchestrator can join.
    """
    now = datetime.now(timezone.utc)
    months = _months_back(now, history_months)
    out: dict[tuple[str, str], list[float]] = {}

    for inv in inventory_records:
        itemnum = str(inv.get("itemnum") or inv.get("spi:itemnum") or "")
        siteid  = str(inv.get("siteid")  or inv.get("spi:siteid")  or "")
        if not itemnum or not siteid:
            continue

        # Q1 simplification: key by plain siteid (not siteid/location) so the
        # generator's lookup matches.  Multi-storeroom per-location vectors are
        # a Q2 enhancement — for now, demand is aggregated across storerooms at
        # the same site, which is correct for site-level ROP optimization.
        warehouse_id = siteid

        # Prefer the sub-collection reference on the inventory record.
        coll_ref = (
            inv.get("matusetrans_collectionref")
            or inv.get("spi:matusetrans_collectionref")
        )
        if coll_ref:
            params = {
                "oslc.select": "actualdate,quantity,transtype",
                "oslc.pageSize": str(_PAGE_SIZE),
            }
            data = await _get_json(coll_ref, settings, params)
            rows = (data or {}).get("member") or (data or {}).get("rdfs:member") or []
        else:
            # Fallback: query MXAPIMATUSETRANS object structure directly.
            base = settings.maximo_base_url.rstrip("/")
            url = f"{base}/api/os/MXAPIMATUSETRANS"
            params = {
                "oslc.select": "actualdate,quantity,transtype",
                "oslc.where":  f'itemnum="{itemnum}" and siteid="{siteid}"',
                "oslc.pageSize": str(_PAGE_SIZE),
            }
            data = await _get_json(url, settings, params)
            rows = (data or {}).get("member") or (data or {}).get("rdfs:member") or []

        if not rows:
            # Don't insert empty rows — the engine will skip these and the
            # heuristic path will pick them up.
            continue

        out[(itemnum, warehouse_id)] = _aggregate_monthly(rows, months)

    logger.info("Fetched demand history for %d (item, warehouse) combinations", len(out))
    return out
