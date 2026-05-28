"""
IBM watsonx.ai driver — Granite / Llama / Mixtral.

Config (.env):
    LLM_PROVIDER=watsonx
    LLM_ENDPOINT=https://us-south.ml.cloud.ibm.com   (or region-specific)
    LLM_API_KEY=<IBM Cloud API key>
    LLM_MODEL=ibm/granite-13b-chat-v2                 (or any supported model)
    LLM_PROJECT_ID=<watsonx project GUID>
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.llm.gateway import LLMDriver, Message

logger = logging.getLogger(__name__)

try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    _IMPORT_OK = True
except Exception:
    _IMPORT_OK = False


class WatsonxDriver(LLMDriver):
    def __init__(self) -> None:
        if not _IMPORT_OK:
            raise RuntimeError("ibm-watsonx-ai package not installed")
        settings = get_settings()
        if not settings.llm_api_key or not settings.llm_project_id:
            raise RuntimeError("LLM_API_KEY and LLM_PROJECT_ID required for watsonx")
        creds = Credentials(
            url=settings.llm_endpoint or "https://us-south.ml.cloud.ibm.com",
            api_key=settings.llm_api_key,
        )
        self._model = ModelInference(
            model_id=settings.llm_model or "ibm/granite-13b-chat-v2",
            credentials=creds,
            project_id=settings.llm_project_id,
        )

    async def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        # watsonx SDK is synchronous — wrap in a thread.
        import asyncio
        prompt = "\n\n".join(
            f"<|{m.role}|>\n{m.content}" for m in messages
        ) + "\n<|assistant|>\n"
        result = await asyncio.to_thread(
            self._model.generate_text,
            prompt=prompt,
            params={
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "decoding_method": "greedy" if temperature < 0.1 else "sample",
            },
        )
        return str(result or "")
