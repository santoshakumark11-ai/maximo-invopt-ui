"""
Ask-the-planner chat service.

The planner asks questions about a specific recommendation.  The LLM
has tool-calling access to:
    - /v1/forecasts/{item}/{warehouse}   (demand history + forecast)
    - /v1/recommendations/{rec_id}       (recommendation detail)
    - /v1/substitutes/{item}             (substitute items)

The tool results are injected into the conversation as assistant context
so the LLM can answer "why is ROP 18?", "show me 12-month consumption",
"what if β=0.95?", etc.

This is a SYNCHRONOUS request/response model (not streaming) for Q2.
Streaming is a Q3 enhancement.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.llm.gateway import Message, complete as llm_complete
from app.recommendations import service as rec_service
from app.substitution.recommender import find_substitutes

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an inventory optimisation assistant helping a Maximo planner.
You have access to the recommendation detail, demand forecast, and
substitute items for the item being discussed.

Rules:
- Answer based ONLY on the data provided in the conversation context.
- Cite specific numbers (ROP, demand, lead time, cost) from the data.
- When the planner asks "what if" questions, reason through the formula
  but clarify this is a simulation, not an actual system change.
- Keep answers concise (3-5 sentences) unless the planner asks for detail.
- Do not invent data.  If the data doesn't contain the answer, say so.
"""


async def _gather_context(rec_id: Optional[str]) -> dict[str, Any]:
    """
    Pre-fetch all the data the LLM might need.

    With rec_id  → full context for that one recommendation
                   (rec + forecast + substitutes).
    Without rec_id → summary of the queue (counts by status / criticality /
                   top items by working-capital release) so the LLM can
                   answer general planner questions like "how many open
                   recommendations do I have?"

    This is the seam where Maximo MCP tool-calling will plug in.  In the
    next iteration, instead of pre-fetching, the LLM will be given a list
    of MCP tool descriptors and choose which to call (mxapi.inventory.get,
    mxapi.po.list, mxapi.matusetrans.get, etc.).
    """
    context: dict[str, Any] = {}

    # ── General context (always included) ────────────────────────────────
    try:
        from collections import Counter
        all_recs = await rec_service.list_all()
        context["queue_summary"] = {
            "totalRecommendations": len(all_recs),
            "byStatus":  dict(Counter(r.status      for r in all_recs)),
            "byType":    dict(Counter(r.type        for r in all_recs)),
            "byCriticality": dict(Counter(r.criticality for r in all_recs)),
            "totalWorkingCapitalRelease": round(
                sum(r.delta_working_capital for r in all_recs if r.status in ("NEW","PENDING","APPROVED")),
                2,
            ),
        }
    except Exception:
        pass

    if not rec_id:
        return context

    rec = await rec_service.get_one(rec_id)
    if rec is None:
        context["error"] = f"recommendation {rec_id} not found"
        return context

    context["recommendation"] = {
        "recId": rec.rec_id,
        "itemId": rec.item_id,
        "itemDescription": rec.item_description,
        "warehouseId": rec.warehouse_id,
        "type": rec.type,
        "criticality": rec.criticality,
        "currentValue": rec.current_value,
        "recommendedValue": rec.recommended_value,
        "deltaWorkingCapital": rec.delta_working_capital,
        "confidence": rec.confidence,
        "modelVersion": rec.model_version,
        "rationale": {
            "demandPattern": rec.rationale.demand_pattern,
            "adi": rec.rationale.adi,
            "cvSquared": rec.rationale.cv_squared,
            "twelveMonthMeanQty": rec.rationale.twelve_month_mean_qty,
            "leadTimeDaysMean": rec.rationale.lead_time_days_mean,
            "leadTimeDaysStd": rec.rationale.lead_time_days_std,
            "serviceLevelTarget": rec.rationale.service_level_target,
        },
        "featureContributions": [
            {"name": f.name, "value": f.value, "contribution": f.contribution}
            for f in rec.feature_contributions
        ],
        "vendor": {
            "vendorId": rec.vendor.vendor_id,
            "name": rec.vendor.name,
            "meanLeadDays": rec.vendor.mean_lead_days,
            "onTimePct": rec.vendor.on_time_pct,
            "unitCost": rec.vendor.unit_cost,
        },
    }

    # Fetch forecast data.
    try:
        from app.forecasts import store as fc_store
        fc = fc_store.get_forecast(rec.item_id, rec.warehouse_id)
        if fc:
            context["forecast"] = {
                "history": [{"month": p.month, "qty": p.qty} for p in fc.history[-6:]],
                "forecast": [{"month": p.month, "mean": p.mean, "p10": p.p10, "p90": p.p90}
                             for p in fc.forecast[:6]],
            }
    except Exception:
        pass

    # Fetch substitute candidates.
    try:
        subs = find_substitutes(rec.item_id, top_k=5)
        if subs:
            context["substitutes"] = [
                {"itemId": s.item_id, "description": s.description,
                 "score": s.score, "stockOnHand": s.stock_on_hand}
                for s in subs
            ]
    except Exception:
        pass

    return context


async def chat(
    *,
    rec_id: Optional[str] = None,
    user_message: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """
    Process one chat turn.  rec_id is optional — when absent, the chat
    operates as a general planner assistant with queue summary context.
    """
    context = await _gather_context(rec_id)

    messages: list[Message] = [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(
            role="system",
            content=f"Context data (do NOT show raw JSON to the user):\n{json.dumps(context, default=str, indent=2)[:3000]}",
        ),
    ]

    # Append conversation history if this is a multi-turn chat.
    for turn in (conversation_history or []):
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append(Message(role=role, content=content))

    messages.append(Message(role="user", content=user_message))

    try:
        return await llm_complete(messages)
    except Exception as exc:
        logger.warning("Chat LLM call failed for rec %s: %s", rec_id, exc)
        return (
            "I'm unable to process your question right now. "
            "Please check that the LLM provider is configured in .env and try again."
        )
