"""
LLM gateway — provider-agnostic abstraction.

Drivers:
    mock          — returns templated text, no external call (default, dev/test).
    azure_openai  — Azure OpenAI GPT-4o / GPT-4o-mini.
    watsonx       — IBM watsonx.ai Granite / Llama / Mixtral.

Config: LLM_PROVIDER + LLM_ENDPOINT + LLM_API_KEY + LLM_MODEL in .env.
"""
