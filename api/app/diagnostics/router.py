"""
Diagnostics router — /v1/diagnostics

Operator-facing endpoints that probe each Maximo data fetcher against ONE
item and return exactly what was sent, what was received, and what was
parsed.  Useful for first-run debugging when :run returns zeros.

Also includes /v1/diagnostics/llm which sanity-checks the LLM gateway —
returns the active driver type, model, response latency, and the actual
text the LLM produced.  Lets the operator confirm a real provider is wired
(not the silent mock fallback).

Protected by JWT (same as all other endpoints) but does not enforce group
RBAC — any authenticated user can call these.
"""
from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

UserDep     = Annotated[CurrentUser, Depends(get_current_user)]
SettingsDep = Annotated[Settings,    Depends(get_settings)]


@router.get("/maximo", summary="Probe each Maximo fetcher for one item")
async def probe_maximo(
    settings: SettingsDep,
    _user:    UserDep,
    item:     Annotated[str, Query(description="itemnum to probe")],
    site:     Annotated[str, Query(description="siteid to probe")],
) -> dict[str, Any]:
    """
    Calls each of the three data fetchers against one (item, site) and reports:
      - inventory: whether the item exists and what fields are present.
      - demand:    how many MATUSETRANS rows were found and the monthly vector.
      - leadtime:  how many receipt/PO observations were found and the days vector.
      - vendor:    whether a VendorInfo was resolved and the source (inventory/item/company).

    Use this after a :run with zeros to pinpoint which Maximo OS is
    unreachable or returning an unexpected shape.
    """
    results: dict[str, Any] = {}

    # ── Inventory probe ──────────────────────────────────────────────────────
    try:
        from app.metrics.maximo_client import fetch_inventory
        all_inv = await fetch_inventory(settings)
        match = [r for r in all_inv if
                 str(r.get("itemnum") or r.get("spi:itemnum") or "").upper() == item.upper()
                 and str(r.get("siteid") or r.get("spi:siteid") or "").upper() == site.upper()]
        # Filter to the specific item+site; there may be MULTIPLE rows if the
        # item exists at several storerooms (location).
        if match:
            # Dump the FULL raw response for the first match so the operator
            # can see the exact field names + values MAS returned.  Skip href-
            # type fields that are just long URLs.
            raw_sample = {}
            for k, v in match[0].items():
                sk = str(k)
                if sk.endswith("_collectionref") or sk.endswith("href"):
                    continue
                if isinstance(v, str) and v.startswith("http"):
                    continue
                # Include invvendor and invcost children (lists/dicts) — they
                # carry vendor + cost data the operator needs to see.
                raw_sample[sk] = v
            results["inventory"] = {
                "found":           True,
                "matching_rows":   len(match),
                "raw_fields":      raw_sample,
                "has_matusetrans_collref": bool(
                    match[0].get("matusetrans_collectionref")
                    or match[0].get("spi:matusetrans_collectionref")
                ),
                "storerooms": [
                    str(r.get("location") or r.get("spi:location") or "?")
                    for r in match
                ],
            }
        else:
            results["inventory"] = {"found": False, "total_records_fetched": len(all_inv)}
    except Exception as exc:
        results["inventory"] = {"error": str(exc)}

    # ── Demand probe ─────────────────────────────────────────────────────────
    try:
        from app.maximo_data.demand import fetch_demand_for_inventory_records
        inv_subset = [r for r in all_inv if
                      str(r.get("itemnum") or r.get("spi:itemnum") or "").upper() == item.upper()
                      and str(r.get("siteid") or r.get("spi:siteid") or "").upper() == site.upper()]
        demand = await fetch_demand_for_inventory_records(inv_subset, settings, history_months=24)
        if demand:
            key = list(demand.keys())[0]
            vec = demand[key]
            results["demand"] = {
                "found": True, "key": list(key),
                "nonzero_months": sum(1 for v in vec if v > 0),
                "total_qty":     round(sum(vec), 1),
                "vector_tail_6": vec[-6:],
            }
        else:
            results["demand"] = {"found": False, "note": "No MATUSETRANS ISSUE rows for this item."}
    except Exception as exc:
        results["demand"] = {"error": str(exc)}

    # ── Lead-time probe ──────────────────────────────────────────────────────
    try:
        from app.maximo_data.leadtime import fetch_lead_times
        inv_subset = [r for r in all_inv if
                      str(r.get("itemnum") or r.get("spi:itemnum") or "").upper() == item.upper()
                      and str(r.get("siteid") or r.get("spi:siteid") or "").upper() == site.upper()]
        lt = await fetch_lead_times(inv_subset, settings, history_months=24)
        if lt:
            key = list(lt.keys())[0]
            days = lt[key]
            results["leadtime"] = {
                "found": True, "key": list(key),
                "observations": len(days),
                "mean_days":    round(sum(days) / len(days), 1) if days else 0,
                "min_days":     round(min(days), 1) if days else 0,
                "max_days":     round(max(days), 1) if days else 0,
            }
        else:
            results["leadtime"] = {
                "found": False,
                "note": ("No PO/receipt data found.  Check that MXAPIPO is "
                         "exposed in this tenant and the item has received POs."),
            }
    except Exception as exc:
        results["leadtime"] = {"error": str(exc)}

    # ── Vendor probe ─────────────────────────────────────────────────────────
    try:
        from app.maximo_data.vendor import fetch_vendor_blocks
        inv_subset = [r for r in all_inv if
                      str(r.get("itemnum") or r.get("spi:itemnum") or "").upper() == item.upper()
                      and str(r.get("siteid") or r.get("spi:siteid") or "").upper() == site.upper()]
        vb = await fetch_vendor_blocks(inv_subset, settings)
        if vb:
            key = list(vb.keys())[0]
            v = vb[key]
            results["vendor"] = {
                "found": True, "key": list(key),
                "vendor_id": v.vendor_id, "name": v.name,
                "unit_cost": v.unit_cost,
            }
        else:
            results["vendor"] = {
                "found": False,
                "note": ("No vendor resolved.  Check MXAPIITEM.vendor or "
                         "MXAPIINVENTORY.vendor in the tenant."),
            }
    except Exception as exc:
        results["vendor"] = {"error": str(exc)}

    return results


# ── LLM gateway sanity check ─────────────────────────────────────────────────

@router.get("/llm", summary="Sanity-check the LLM gateway and active driver")
async def probe_llm(
    settings: SettingsDep,
    _user:    UserDep,
    prompt:   Annotated[str, Query(description="Test prompt to send to the LLM")] =
              "In one short sentence, state the formula for Economic Order Quantity.",
) -> dict[str, Any]:
    """
    Exercises the configured LLM provider with a known prompt and returns:
      - configured_provider: the value of LLM_PROVIDER from .env
      - actual_driver:       the driver class actually loaded (reveals fallback to mock)
      - model:               the model name the driver is using
      - response:            the LLM's actual response text
      - elapsed_ms:          round-trip latency
      - error:               present only if the call failed

    A successful response with `actual_driver != "MockDriver"` proves the
    real provider is wired.  If you see `MockDriver` here while LLM_PROVIDER
    is set to openai/azure_openai/watsonx, the driver failed to load — most
    likely missing LLM_API_KEY or the SDK package isn't installed.
    """
    from app.llm.gateway import get_driver, complete, Message

    out: dict[str, Any] = {
        "configured_provider": settings.llm_provider,
        "actual_driver": None,
        "model": None,
        "response": None,
        "elapsed_ms": None,
        "error": None,
    }

    try:
        driver = get_driver()
        out["actual_driver"] = type(driver).__name__
        # Best-effort model extraction (each driver stores it differently).
        for attr in ("_model", "_deployment"):
            if hasattr(driver, attr):
                out["model"] = getattr(driver, attr)
                break
        out["model"] = out["model"] or settings.llm_model or settings.llm_deployment or "(default)"
    except Exception as exc:
        out["error"] = f"driver init failed: {exc}"
        return out

    start = time.monotonic()
    try:
        text = await complete([
            Message(role="system",
                    content="You are a concise inventory analyst.  Reply in one sentence."),
            Message(role="user", content=prompt),
        ], max_tokens=120, temperature=0.1)
        out["response"] = text
    except Exception as exc:
        out["error"] = f"completion failed: {exc}"

    out["elapsed_ms"] = round((time.monotonic() - start) * 1000, 1)

    # Heuristic: the mock driver always echoes "[Mock LLM" — call it out.
    if isinstance(out["response"], str) and out["response"].startswith("[Mock LLM"):
        out["warning"] = (
            "Response was generated by the mock driver.  Set LLM_PROVIDER and "
            "LLM_API_KEY in .env, then restart uvicorn."
        )

    return out
