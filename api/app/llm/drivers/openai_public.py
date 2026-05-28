"""
Public OpenAI driver — GPT-4o-mini / GPT-4o / o1-mini etc. via api.openai.com.

Use this when you have a direct OpenAI API key (sk-...).  Use the
azure_openai driver instead when the model is hosted on Azure.

Config (.env):
    LLM_PROVIDER=openai
    LLM_API_KEY=sk-...                     # OpenAI secret key
    LLM_MODEL=gpt-4o-mini                  # or gpt-4o, o1-mini, gpt-4.1-mini, etc.
    LLM_ENDPOINT=                          # leave blank for OpenAI; set to a proxy URL otherwise

Cost-wise, gpt-4o-mini is the cheapest current chat model (~$0.15 / $0.60
per 1M input / output tokens).  Rationale + chat use < 1k tokens per turn,
so a planner doing 100 chat turns / day costs roughly cents.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.llm.gateway import LLMDriver, Message

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    _IMPORT_OK = True
except Exception:
    _IMPORT_OK = False


class OpenAIDriver(LLMDriver):
    def __init__(self) -> None:
        if not _IMPORT_OK:
            raise RuntimeError("openai package not installed")
        settings = get_settings()
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY required for openai provider")

        # base_url is optional — empty means api.openai.com.  Set it to point
        # at a self-hosted gateway (LiteLLM, Helicone, etc.) if needed.
        kwargs = {"api_key": settings.llm_api_key}
        if settings.llm_endpoint:
            kwargs["base_url"] = settings.llm_endpoint
        self._client = AsyncOpenAI(**kwargs)
        self._model = settings.llm_model or "gpt-4o-mini"

    async def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        kwargs: dict = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        _apply_model_kwargs(self._model, kwargs, max_tokens, temperature)
        resp = await self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


# ── OpenAI model-family quirks ───────────────────────────────────────────────

# Models that require max_completion_tokens (and reject max_tokens):
#   gpt-5.x, o1, o3, o4 series (reasoning + newer chat).
# These same models also reject custom temperature — only the default (1.0)
# is allowed.  Older models (gpt-3.5, gpt-4, gpt-4o, gpt-4o-mini, gpt-4.1)
# continue to accept the legacy max_tokens + temperature kwargs.
_NEW_PARAM_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _apply_model_kwargs(model: str, kwargs: dict, max_tokens: int, temperature: float) -> None:
    model_lc = model.lower()
    if any(model_lc.startswith(p) for p in _NEW_PARAM_PREFIXES):
        kwargs["max_completion_tokens"] = max_tokens
        # No temperature — these models lock it to 1.0.
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
