"""
Orchestration — single async run_batch() ties together the read path
(MXAPIINVENTORY, MATUSETRANS, MATRECTRANS, COMPANIES) and the write path
(generator → service → audit → metrics).

Called from:
  - the FastAPI lifespan (best-effort, on startup)
  - POST /v1/recommendations:run (on demand)
  - POST /v1/forecasts:refresh    (on demand, forecasts only)
  - APScheduler nightly cron      (when SCHEDULER_ENABLED=true)

The orchestrator is the SAME function in every case so a manual :run produces
the same artefacts as the nightly batch — no two code paths to maintain.
"""
