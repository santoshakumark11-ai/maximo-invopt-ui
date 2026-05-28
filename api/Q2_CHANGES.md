# Q2 — Substitutes, Agent, LLM rationale, Chat

Q1.1 + Q1.2 produced a working engine; Q2 makes the AI surfaces a customer can see.

## Q2.1 — Substitution recommender (DLD §4.4, §7.3, §8.4)

| File | Role |
|---|---|
| `app/substitution/embeddings.py` | Item-description embeddings via sentence-transformers (`all-MiniLM-L6-v2`, 384-dim CPU). Falls back to TF-IDF + TruncatedSVD when sentence-transformers is unavailable (Python 3.13 today). |
| `app/substitution/recommender.py` | Hybrid retrieval — cross-ref first (deterministic ALTITEM cache), then embedding cosine top-K, then composite-score rerank per DLD §8.4 weights (0.45 cross-ref + 0.25 cosine + 0.15 co-use + 0.10 stock + 0.05 vendor). |
| `app/substitution/router.py` | `GET /v1/substitutes/{item}?top_k=10` |
| Orchestrator hook | After each `run_batch`, the embedding index is rebuilt from the inventory pull, and the inventory snapshot is loaded into the recommender for stock-on-hand scoring. |

## Q2.1 — Agentic auto-apply (DLD §4.1, principle P-3)

| File | Role |
|---|---|
| `app/agent/policy.py` | Per-tenant policy engine — checks status, criticality, type, delta-WC threshold, AND cross-checks open PO quantity (won't auto-reduce ROP if a large PO is in transit). |
| `app/agent/executor.py` | Reads NEW recs, evaluates policy, auto-approves and (if `WRITEBACK_ENABLED=true`) fans out to the writeback saga. Every action lands in WORM audit with `principal="agent"`. |
| `POST /v1/agent:run` | Operator trigger. Wired into `main.py`. |
| Orchestrator hook | After each `run_batch`, if `AGENT_AUTO_APPLY_ENABLED=true`, the agent runs against the freshly-generated NEW recs. |

Default is OFF. Operator flips `AGENT_AUTO_APPLY_ENABLED=true` after confirming recommendation quality.

## Q2.2 — LLM gateway (DLD §11.2 LLM redaction at gateway)

| File | Role |
|---|---|
| `app/llm/gateway.py` | Abstract `LLMDriver` + driver registry. Picks `mock`, `azure_openai`, or `watsonx` based on `LLM_PROVIDER`. |
| `app/llm/drivers/mock.py` | Default. No external call — returns templated text. Used in tests + when no provider is configured. |
| `app/llm/drivers/azure_openai.py` | Async Azure OpenAI via `openai` SDK. Reads `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_DEPLOYMENT`. |
| `app/llm/drivers/watsonx.py` | IBM watsonx.ai via `ibm-watsonx-ai`. Reads `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROJECT_ID`. |

## Q2.2 — LLM rationale per recommendation

| File | Role |
|---|---|
| `app/llm/rationale.py` | Takes structured (pattern, ADI, CV², β, features, delta) → defensible paragraph via the gateway. Cached by SHA-256 of (item, warehouse, model_version, recommended_value) so stable across runs. Falls back to the engine's f-string text on LLM failure. |
| `POST /v1/recommendations/{recId}/rationale` | On-demand regeneration. |
| Orchestrator hook | When `LLM_PROVIDER != "mock"`, the orchestrator regenerates the rationale for the top 10 recs after each batch. |

## Q2.2 — Ask-the-planner chat

| File | Role |
|---|---|
| `app/llm/chat.py` | Multi-turn chat. Pre-fetches recommendation + forecast + substitutes for the rec being discussed and injects as system context. The LLM answers without seeing raw JSON in the UI. |
| `POST /v1/recommendations/{recId}/chat` | Body: `{message, history?}` → `{reply, recId}`. |
| `web/dashboard/src/features/detail/ChatPanel.tsx` | Carbon UI panel rendered on the RecommendationDetail page. Suggested-question chips for first-time users. |

## Operator quickstart

```powershell
cd D:\GitRepo\maximo-invopt-ui\api

# Pull new deps (sentence-transformers / openai / ibm-watsonx-ai are optional)
python -m pip install -r requirements.txt

# Reload tables — no new migration needed (no schema change in Q2)
uvicorn app.main:app --reload

# In another shell:
$headers = @{ Authorization = "Bearer $jwt" }

# 1. Re-run the batch.  The orchestrator now builds the embedding index +
#    runs the agent (if enabled) + regenerates LLM rationales (if configured).
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/v1/recommendations:run" -Headers $headers

# 2. Try the substitution recommender against any item.
Invoke-RestMethod -Uri "http://localhost:8000/v1/substitutes/11453" -Headers $headers | ConvertTo-Json -Depth 4

# 3. Try the chat against a recommendation.
$body = @{ message = "Why is the ROP this number?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/v1/recommendations/REC-0001/chat" `
                  -Headers $headers -ContentType "application/json" -Body $body

# 4. Run the agent on demand (still OFF by default — flip AGENT_AUTO_APPLY_ENABLED first).
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/v1/agent:run" -Headers $headers
```

## LLM provider configuration

Configure ONE of these blocks in `.env`:

```ini
# Mock (default — no external calls, templated text)
LLM_PROVIDER=mock

# Azure OpenAI
LLM_PROVIDER=azure_openai
LLM_ENDPOINT=https://<resource>.openai.azure.com/
LLM_API_KEY=<key>
LLM_DEPLOYMENT=gpt-4o-mini

# IBM watsonx.ai
LLM_PROVIDER=watsonx
LLM_ENDPOINT=https://us-south.ml.cloud.ibm.com
LLM_API_KEY=<IBM Cloud API key>
LLM_MODEL=ibm/granite-13b-chat-v2
LLM_PROJECT_ID=<watsonx project GUID>
```

## What is still off by default

- `AGENT_AUTO_APPLY_ENABLED=false` — must be flipped explicitly per tenant.
- `LLM_PROVIDER=mock` — must be set to `azure_openai` or `watsonx` to get real rationales.
- `WRITEBACK_ENABLED=false` (carried over from Q1) — the agent will auto-approve but not push to Maximo until this is flipped too.

## What did NOT change

- Auth (per your instruction). Still Maximo personal API key + HS256 JWT.
- The DLD §6.3 failure-signal subscriber (Kafka). Deferred per your scope decision.
- OIDC migration. Deferred per your scope decision.
