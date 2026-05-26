"""
Maximo client for per-item demand history via the MATUSETRANS sub-collection.

MATUSETRANS is exposed as a relationship inside MXAPIINVENTORY.  Each inventory
record's response contains a 'matusetrans_collectionref' URL that we follow to
retrieve that item's transaction history.

Flow:
  1. Query MXAPIINVENTORY with oslc.where=itemnum=X and siteid=Y to get the
     matusetrans_collectionref URL for that specific record.
  2. Fetch that URL with oslc.select=actualdate,quantity,transtype.
  3. Aggregate ISSUE transactions by YYYY-MM.
  4. Build a ForecastSeries: 12 months history + 6 months simple-trend forecast.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.forecasts.models import ForecastPoint, ForecastSeries, HistoryPoint

logger = logging.getLogger(__name__)

_TRANS_PAGE_SIZE = 500


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.maximo_api_key,
        "Accept": "application/json",
    }


async def _fetch(
    url: str,
    settings: Settings,
    params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """GET a Maximo URL and return the member list, or [] on any error."""
    try:
        async with httpx.AsyncClient(
            verify=False, timeout=settings.maximo_timeout
        ) as client:
            resp = await client.get(url, headers=_headers(settings), params=params or {})
    except httpx.RequestError as exc:
        logger.warning("Maximo request failed: %s", exc)
        return []

    if not resp.is_success:
        logger.warning("Maximo returned HTTP %s for %s", resp.status_code, url)
        return []

    try:
        data = resp.json()
    except Exception:
        logger.warning("Non-JSON response from %s", url)
        return []

    return data.get("member") or data.get("rdfs:member") or []


# ── Collection ref lookup ─────────────────────────────────────────────────────

async def _get_matusetrans_url(
    settings: Settings,
    itemnum: str,
    siteid: str,
) -> str | None:
    """
    Find the MXAPIINVENTORY record for item × site and return its
    matusetrans_collectionref URL.
    """
    base = settings.maximo_base_url.rstrip("/")
    members = await _fetch(
        f"{base}/api/os/MXAPIINVENTORY",
        settings,
        params={
            "oslc.select": "itemnum,siteid",
            "oslc.where": f'itemnum="{itemnum.upper()}" and siteid="{siteid.upper()}"',
            "oslc.pageSize": "1",
        },
    )
    if not members:
        return None
    url = members[0].get("matusetrans_collectionref")
    logger.debug("matusetrans_collectionref for %s/%s: %s", itemnum, siteid, url)
    return url


# ── Forecast builder ──────────────────────────────────────────────────────────

def _month_key(date_str: str) -> str | None:
    """Extract YYYY-MM from an ISO date string, or None if unparseable."""
    if date_str and len(date_str) >= 7:
        return date_str[:7]
    return None


def _project_forecast(history: list[HistoryPoint], months: int = 6) -> list[ForecastPoint]:
    """
    Simple linear-trend projection from the last 3 history points.
    Returns `months` ForecastPoint objects starting the month after history ends.
    """
    qty_series = [h.qty for h in history]
    last_3 = qty_series[-3:] if len(qty_series) >= 3 else qty_series
    base = sum(last_3) / len(last_3) if last_3 else 0.0
    trend = (last_3[-1] - last_3[0]) / max(len(last_3) - 1, 1) if len(last_3) >= 2 else 0.0

    points: list[ForecastPoint] = []
    # Start from the month after the last history month
    last_month = history[-1].month if history else date.today().strftime("%Y-%m")
    year, month = int(last_month[:4]), int(last_month[5:7])

    for i in range(1, months + 1):
        month += 1
        if month > 12:
            month = 1
            year += 1
        mean = round(max(0.0, base + trend * i), 2)
        spread = round(mean * 0.25, 2)
        points.append(ForecastPoint(
            month=f"{year:04d}-{month:02d}",
            mean=mean,
            p10=round(max(0.0, mean - spread), 2),
            p90=round(mean + spread, 2),
        ))
    return points


async def fetch_item_forecast(
    settings: Settings,
    itemnum: str,
    siteid: str,
) -> ForecastSeries | None:
    """
    Fetch MATUSETRANS history for item × site and build a ForecastSeries.
    Returns None if the item is not found or has no transaction history.
    """
    trans_url = await _get_matusetrans_url(settings, itemnum, siteid)
    if not trans_url:
        logger.info("No MXAPIINVENTORY record for %s / %s", itemnum, siteid)
        return None

    transactions = await _fetch(
        trans_url,
        settings,
        params={
            "oslc.select": "actualdate,quantity,transtype",
            "oslc.pageSize": str(_TRANS_PAGE_SIZE),
        },
    )
    if not transactions:
        logger.info("No transactions found for %s / %s", itemnum, siteid)
        return None

    # Aggregate issued quantities by month
    monthly: dict[str, float] = defaultdict(float)
    for t in transactions:
        ttype = (t.get("transtype") or t.get("spi:transtype") or "").upper()
        # Include ISSUE transactions; if transtype is blank include everything
        if ttype and ttype not in ("ISSUE", "RETURN"):
            continue
        date_str = str(t.get("actualdate") or t.get("spi:actualdate") or "")
        mk = _month_key(date_str)
        if not mk:
            continue
        try:
            qty = abs(float(t.get("quantity") or t.get("spi:quantity") or 0))
        except (TypeError, ValueError):
            qty = 0.0
        monthly[mk] += qty

    if not monthly:
        logger.info("No usable transactions for %s / %s", itemnum, siteid)
        return None

    # Build 12-month history window ending at the current month
    today = date.today()
    history: list[HistoryPoint] = []
    for i in range(11, -1, -1):
        # Step back month by month
        d = today.replace(day=1)
        for _ in range(i):
            d = (d - timedelta(days=1)).replace(day=1)
        mk = d.strftime("%Y-%m")
        history.append(HistoryPoint(month=mk, qty=round(monthly.get(mk, 0.0), 1)))

    forecast = _project_forecast(history)

    logger.info(
        "Built forecast for %s/%s — %d history months, max qty %.1f",
        itemnum, siteid, len(history), max((h.qty for h in history), default=0),
    )

    return ForecastSeries(
        item_id=itemnum,
        warehouse_id=siteid,
        history=history,
        forecast=forecast,
        recommended_reorder_point=0.0,
        recommended_safety_stock=0.0,
        model_version="matusetrans/linear-v1",
        as_of=today.isoformat() + "T00:00:00Z",
    )
