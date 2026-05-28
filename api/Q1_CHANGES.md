# Q1 critical-fix landings

This document lists what changed in the API as part of the Q1.1 + Q1.2 work
described in `REQ-003_Codebase_vs_Design_Gap_Analysis.docx`. Auth is **not**
touched — Maximo personal API-key + HS256 JWT remains the login model.

## Q1.1 Foundations

| Concern | New / updated files | Notes |
|---|---|---|
| DB persistence | `app/db.py`, `app/models_db.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py` | SQLite for dev, Postgres in prod. `PERSISTENCE_ENABLED=false` returns the API to the in-memory demo path. |
| Repo + service layer | `app/recommendations/repo.py`, `app/recommendations/service.py` | Async surface used by the router. Picks DB vs in-memory at runtime. |
| WORM audit | `app/audit.py`, `audit_events` table | Append-only with HMAC-SHA256 chain; `verify_chain(rec_id)` walks back. |
| Maximo writeback saga | `app/writeback/maximo.py`, `app/writeback/saga.py` | POSTs `MXINV_INVENTORY_V1` with ROWSTAMP optimistic concurrency, retries on 409, marks `FAILED` on exhaustion. Gated by `WRITEBACK_ENABLED`. |
| Observability | `app/observability/logging.py`, `app/observability/metrics.py` | Structured JSON logs + correlation-id middleware. Prometheus `/metrics` via `prometheus_fastapi_instrumentator`. Six DLD §12.1 custom instruments. |
| Health endpoints | `app/main.py` adds `/healthz` (was already present) and a new `/readyz` that checks DB + Maximo. | |
| CI | `.github/workflows/api-ci.yml`, `.github/workflows/ui-ci.yml` | Lint + typecheck + tests + docker build for the API. Typecheck + lint + vitest + playwright + build for the UI. |

## Q1.2 Engine

| Concern | New / updated files | Notes |
|---|---|---|
| Demand-pattern classifier | `app/forecasting/classifier.py` | Syntetos/Boylan ADI + CV² → `{smooth, intermittent, erratic, lumpy, no_demand}`. NumPy + pure-Python fallback. |
| Optimisation engine | `app/optimisation/engine.py` | Normal-model ROP/SS with `scipy.stats.norm.ppf(β)`; Shapiro-Wilk gate; bootstrap quantile fallback. Wilson EOQ with discount-aware total-cost evaluation. β routed from criticality (0.95 / 0.99 / 0.995). |
| Probabilistic forecasting | `app/forecasting/service.py` | Routes per pattern to `statsforecast.AutoETS` (smooth) / `CrostonSBA` (intermittent + lumpy) / bootstrap (erratic). Quantile bands from in-sample residuals. Falls back cleanly when `statsforecast` is unavailable. |
| Backtest harness | `app/forecasting/backtest.py` | Rolling-origin CV → WAPE / MAPE / bias per pattern, persisted to `forecast_backtests`. |
| Generator integration | `app/recommendations/generator.py` | New `build_rop_from_engine(...)` path. When `demand_histories` + `lead_time_histories` are supplied to `generate_from_inventory`, the engine drives the recommendation. The old heuristic remains as the cold-start fallback. |
| Calibration shadow mode | `app/feedback.py`, `planner_feedback` table | Every approve/reject/edit records (raw confidence, features, decision). Calibrator model itself is Q2 — this captures the labels now. |

## Configuration cheatsheet

The new variables in `api/.env.example` are summarised below. Every one has a
sane default — the API runs without changes if you just copy the file.

```
DATABASE_URL=sqlite+aiosqlite:///./invopt.db
PERSISTENCE_ENABLED=true
AUDIT_HMAC_SECRET=<random 32-byte hex>
WRITEBACK_ENABLED=false                # flip to true after MXINV_INVENTORY_V1 is in place
WRITEBACK_OS_NAME=MXINV_INVENTORY_V1
WRITEBACK_MAX_RETRIES=3
PROMETHEUS_ENABLED=true
LOG_JSON=true
LOG_LEVEL=INFO
RECOMMENDATION_DELTA_THRESHOLD_PCT=5.0
SERVICE_LEVEL_NON_CRITICAL=0.95
SERVICE_LEVEL_CRITICAL=0.99
SERVICE_LEVEL_SAFETY_CRITICAL=0.995
FORECASTING_USE_STATSFORECAST=true
```

## Local run after pulling

```powershell
# from D:\GitRepo\maximo-invopt-ui\api
python -m pip install -r requirements.txt

# one-time: create tables (the lifespan also creates them on first start,
# but alembic is what production uses):
alembic upgrade head

uvicorn app.main:app --reload
```

Then `pytest -q` from the same directory runs the new unit tests:

- `tests/test_classifier.py`
- `tests/test_optimisation.py`
- `tests/test_audit.py`
- `tests/test_writeback.py`

## What is still off by default

- `WRITEBACK_ENABLED=false`. The saga code is wired into `/approve` but skipped
  until you flip the flag. This is intentional — the MXINV_INVENTORY_V1 Object
  Structure needs Maximo SME sign-off before any tenant goes live.
- `SCHEDULER_ENABLED=false`. The nightly batch is registered but does not auto-run
  until you flip the flag. The first run is always operator-initiated via
  `POST /v1/recommendations:run`.

## Q1.2 end-to-end wiring (added after the foundations landed)

| Concern | New / updated files | Notes |
|---|---|---|
| MATUSETRANS demand fetcher | `app/maximo_data/demand.py` | Pulls per-(item, warehouse) 24-month issue history; aggregates RETURNs as reversals. |
| MATRECTRANS lead-time fetcher | `app/maximo_data/leadtime.py` | Joins receipts to PO → lead-time-in-days; caches PO header lookups; drops > 365-day outliers. |
| Vendor + INVCOST fetcher | `app/maximo_data/vendor.py` | ITEMORGINFO + COMPANIES → real vendor block. |
| Orchestrator | `app/orchestration/nightly.py` | `run_batch()` ties together inventory + demand + leadtime + vendor → generator → service → audit → metrics → backtest. Same function for manual run and scheduler. |
| On-demand triggers | `app/recommendations/router.py` (+`:run`), `app/forecasts/router.py` (+`:refresh`) | Synchronous endpoints that exercise the orchestrator. |
| Forecast endpoint rewire | `app/forecasts/router.py` | DB cache → live re-forecast via `forecasting.service.forecast()` → static seed only as last resort. |
| Metrics rewire | `app/metrics/router.py` | `working-capital-trend` now cumulates APPLIED recommendations by month; `forecast-accuracy` reads from `forecast_backtests`. Both fall back to the legacy synthetic / seed paths when no real data exists yet. |
| Scheduler | `app/orchestration/scheduler.py` | APScheduler cron — defaults to `0 2 * * *`, off by default. |
| Generator | `app/recommendations/generator.py` | Composite-key (item, warehouse) dispatch; vendor block flows through. |
| Tests | `tests/test_orchestrator.py` | End-to-end batch test with monkeypatched Maximo fetchers. |

## Operator quickstart for Q1.2

```powershell
cd D:\GitRepo\maximo-invopt-ui\api
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Then run the first batch manually.  PowerShell aliases `curl` to
`Invoke-WebRequest`, which uses different syntax — either call `curl.exe`
explicitly, or use `Invoke-RestMethod`:

```powershell
# Option A — real curl (Windows 10/11 ships it as curl.exe)
curl.exe -X POST "http://localhost:8000/v1/recommendations:run" `
         -H "Authorization: Bearer $jwt"

# Option B — PowerShell-native, prettier output
$headers = @{ Authorization = "Bearer $jwt" }
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/v1/recommendations:run" -Headers $headers
```

Check the result:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/v1/recommendations?pageSize=10" -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/v1/metrics/forecast-accuracy"       -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/v1/metrics/working-capital-trend"   -Headers $headers
```

To run a focused batch over a small set of items (faster, useful for first
smoke-tests against a live MAS tenant):

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/v1/recommendations:run?items=PUMP-001,VALVE-042" `
  -Headers $headers
```

Once the manual run looks correct, flip `SCHEDULER_ENABLED=true` in `.env` and
restart.

## What did NOT change

- Auth (per request). `app/auth/*` is untouched. Login still happens with the
  Maximo personal API key; the backend issues an HS256 JWT and the UI stores
  it in `sessionStorage`.
- The Carbon UI. All Q1 work is server-side. Future Q1.x slices can surface
  the new audit + backtest + feedback data on the dashboard, but no UI code
  was modified in this commit.
