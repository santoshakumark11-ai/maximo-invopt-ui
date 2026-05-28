"""
Abstract LLM gateway + driver registry.

All drivers implement `async def complete(messages, **kwargs) -> str`.
The gateway picks the driver from settings.llm_provider at startup.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str    # "system" | "user" | "assistant"
    content: str


class LLMDriver(ABC):
    """One driver per LLM provider."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """Return the assistant's text response."""


# ── Driver registry ──────────────────────────────────────────────────────────

_driver: Optional[LLMDriver] = None


def get_driver() -> LLMDriver:
    global _driver
    if _driver is not None:
        return _driver

    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "azure_openai":
        try:
            from app.llm.drivers.azure_openai import AzureOpenAIDriver
            _driver = AzureOpenAIDriver()
            logger.info("LLM driver: Azure OpenAI")
        except Exception as exc:
            logger.warning("Azure OpenAI driver failed to load (%s) — falling back to mock", exc)
            from app.llm.drivers.mock import MockDriver
            _driver = MockDriver()

    elif provider == "openai":
        try:
            from app.llm.drivers.openai_public import OpenAIDriver
            _driver = OpenAIDriver()
            logger.info("LLM driver: OpenAI (model=%s)", settings.llm_model or "gpt-4o-mini")
        except Exception as exc:
            logger.warning("OpenAI driver failed to load (%s) — falling back to mock", exc)
            from app.llm.drivers.mock import MockDriver
            _driver = MockDriver()

    elif provider == "watsonx":
        try:
            from app.llm.drivers.watsonx import WatsonxDriver
            _driver = WatsonxDriver()
            logger.info("LLM driver: IBM watsonx.ai")
        except Exception as exc:
            logger.warning("watsonx driver failed to load (%s) — falling back to mock", exc)
            from app.llm.drivers.mock import MockDriver
            _driver = MockDriver()

    else:
        from app.llm.drivers.mock import MockDriver
        _driver = MockDriver()
        if provider != "mock":
            logger.warning("Unknown LLM_PROVIDER=%r — using mock driver", provider)
        else:
            logger.info("LLM driver: mock (no external calls)")

    return _driver


async def complete(messages: list[Message], **kwargs) -> str:
    """Convenience wrapper: picks the driver and calls complete."""
    driver = get_driver()
    settings = get_settings()
    return await driver.complete(
        messages,
        max_tokens=kwargs.get("max_tokens", settings.llm_max_tokens),
        temperature=kwargs.get("temperature", settings.llm_temperature),
    )
