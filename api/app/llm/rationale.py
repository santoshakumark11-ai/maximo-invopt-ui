"""
LLM-powered rationale generator — replaces the f-string rationale.

Takes the structured features from a RecommendationDetail and produces
a defensible one-paragraph explanation that a planner can present to
their manager.

Cached by (item_id, model_version) so the same recommendation gets a
stable text — re-running the orchestrator doesn't produce new text for
unchanged recommendations.

PII redaction: item descriptions are passed through; no personal data
(usernames, email, etc.) is sent to the LLM.  The prompt explicitly
forbids the model from inventing numbers.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from app.llm.gateway import Message, complete as llm_complete
from app.recommendations.models import RecommendationDetail

logger = logging.getLogger(__name__)

# Simple in-memory cache — survives until pod restart.
_cache: dict[str, str] = {}

_SYSTEM_PROMPT = """\
You are an inventory optimisation analyst writing for a Maximo planner.
Given the structured data below, write ONE clear paragraph (4-6 sentences)
explaining why this recommendation was made and what the expected impact is.

Rules:
- Use ONLY the numbers provided.  Do not invent or hallucinate any values.
- Reference the demand pattern, service level, lead time, and key feature drivers.
- Quantify the working-capital release in dollars.
- State the trade-off (risk vs cost) concisely.
- Do not use bullet points or headers — flowing prose only.
- Keep language professional but accessible to a non-technical planner.
"""


def _build_user_prompt(rec: RecommendationDetail) -> str:
    features_block = "\n".join(
        f"  - {f.name}: {f.value} (contribution: {f.contribution:.0%})"
        for f in rec.feature_contributions[:8]
    )
    return f"""\
Item: {rec.item_id} — {rec.item_description}
Warehouse: {rec.warehouse_id}
Recommendation type: {rec.type}
Current value: {rec.current_value}
Recommended value: {rec.recommended_value}
Working-capital release: ${rec.delta_working_capital:,.0f}
Confidence: {rec.confidence:.0%}
Model version: {rec.model_version}

Demand pattern: {rec.rationale.demand_pattern}
ADI: {rec.rationale.adi:.2f}
CV²: {rec.rationale.cv_squared:.2f}
12-month mean qty: {rec.rationale.twelve_month_mean_qty:.1f}
Lead time (mean): {rec.rationale.lead_time_days_mean:.0f} days
Lead time (std): {rec.rationale.lead_time_days_std:.1f} days
Service level target (β): {rec.rationale.service_level_target:.1%}

Feature drivers:
{features_block}

Write the rationale paragraph now.
"""


def _cache_key(rec: RecommendationDetail) -> str:
    raw = f"{rec.item_id}|{rec.warehouse_id}|{rec.model_version}|{rec.recommended_value}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def generate_rationale(rec: RecommendationDetail) -> str:
    """
    Generate a natural-language rationale for one recommendation.
    Returns the cached value if available.
    """
    key = _cache_key(rec)
    if key in _cache:
        return _cache[key]

    messages = [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(role="user",   content=_build_user_prompt(rec)),
    ]

    try:
        text = await llm_complete(messages)
        _cache[key] = text
        return text
    except Exception as exc:
        logger.warning("LLM rationale generation failed for %s: %s", rec.rec_id, exc)
        # Fall back to the existing f-string rationale from the engine.
        return rec.rationale.summary_text
