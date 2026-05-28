"""
Azure OpenAI driver — GPT-4o / GPT-4o-mini via the openai SDK.

Config (.env):
    LLM_PROVIDER=azure_openai
    LLM_ENDPOINT=https://<resource>.openai.azure.com/
    LLM_API_KEY=<key>
    LLM_DEPLOYMENT=<deployment-name>      # e.g. gpt-4o-mini
    LLM_MODEL=gpt-4o-mini                 # optional, used for logging
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.llm.gateway import LLMDriver, Message

logger = logging.getLogger(__name__)

try:
    from openai import AsyncAzureOpenAI
    _IMPORT_OK = True
except Exception:
    _IMPORT_OK = False


class AzureOpenAIDriver(LLMDriver):
    def __init__(self) -> None:
        if not _IMPORT_OK:
            raise RuntimeError("openai package not installed")
        settings = get_settings()
        if not settings.llm_endpoint or not settings.llm_api_key:
            raise RuntimeError("LLM_ENDPOINT and LLM_API_KEY required for azure_openai")
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.llm_endpoint,
            api_key=settings.llm_api_key,
            api_version="2024-08-01-preview",
        )
        self._deployment = settings.llm_deployment or settings.llm_model or "gpt-4o-mini"

    async def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        # Newer OpenAI families on Azure (gpt-5.x / o-series) require
        # max_completion_tokens and reject custom temperature.  Older
        # families (gpt-4o, gpt-4o-mini, gpt-4) keep the legacy params.
        from app.llm.drivers.openai_public import _apply_model_kwargs
        kwargs: dict = {
            "model": self._deployment,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        # Use deployment name as the model hint — Azure deployments are
        # commonly named after the underlying model (gpt-4o-mini, gpt-5-mini).
        _apply_model_kwargs(self._deployment, kwargs, max_tokens, temperature)
        resp = await self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
