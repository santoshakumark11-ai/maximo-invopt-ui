"""
Mock LLM driver — returns templated text without calling any external service.
Used for dev, testing, and as the fallback when no LLM provider is configured.
"""
from __future__ import annotations

from app.llm.gateway import LLMDriver, Message


class MockDriver(LLMDriver):
    async def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        # Echo the last user message wrapped in a rationale-style template.
        user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return (
            f"[Mock LLM — no external call]\n\n"
            f"Based on the data provided:\n{user_msg[:500]}\n\n"
            f"This is a mock response. Configure LLM_PROVIDER in .env to "
            f"'azure_openai' or 'watsonx' for real rationale generation."
        )
