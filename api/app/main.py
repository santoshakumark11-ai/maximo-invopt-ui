"""
Inventory Optimisation Agent — API
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.auth.router import router as auth_router
from app.metrics.router import router as metrics_router
from app.recommendations.router import router as rec_router
from app.forecasts.router import router as fc_router
from app.diagnostics.router import router as diag_router
from app.substitution.router import router as sub_router
from app.llm.router import router as llm_router, general_router as chat_router

# ── Q1.1: structured logging — falls back to basicConfig if module fails to load ──
try:
    from app.observability.logging import configure_logging, correlation_id_middleware
    configure_logging()
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    correlation_id_middleware = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Inventory Optimisation API")
    logger.info("Maximo base URL: %s", settings.maximo_base_url)
    logger.info("Environment: %s", settings.app_env)

    # ── Q1.1: init DB (best-effort; falls back to in-memory) ────────────────
    try:
        from app import db as db_module
        db_ready = await db_module.init_db(settings)
        if db_ready:
            logger.info("DB persistence enabled")
        else:
            logger.info("DB persistence disabled — using in-memory store")
    except Exception as exc:
        logger.warning("DB init raised (%s) — using in-memory store", exc)

    # Seed recommendations from live Maximo inventory on startup.
    #
    # Behaviour matrix:
    #   Maximo reachable, records returned  → service.seed_from_live_data()
    #                                         clears the active store and
    #                                         populates with live results
    #                                         (even if 0 qualify — no fake data)
    #   Maximo reachable, 0 records         → service.seed_from_live_data() clears store
    #   Maximo unreachable / exception      → leave hardcoded seed intact
    try:
        from app.metrics.maximo_client import fetch_inventory
        from app.recommendations import service as rec_service
        records = await fetch_inventory(settings)
        if records:
            n = await rec_service.seed_from_live_data(records)
            logger.info(
                "Startup: seeded %d live recommendations from %d inventory records",
                n, len(records),
            )
        else:
            logger.warning(
                "Startup: MXAPIINVENTORY returned 0 records — "
                "keeping hardcoded seed recommendations"
            )
    except Exception as exc:
        logger.warning(
            "Startup: recommendation seeding failed (%s) — keeping hardcoded seed", exc
        )

    # ── Q1.2: optional APScheduler nightly batch ───────────────────────────
    try:
        from app.orchestration import scheduler as sched_module
        sched_module.start()
    except Exception as exc:
        logger.warning("Scheduler bootstrap failed: %s", exc)

    yield

    # ── Shutdown ────────────────────────────────────────────────────────────
    try:
        from app.orchestration import scheduler as sched_module
        await sched_module.stop()
    except Exception:
        pass
    try:
        from app import db as db_module
        await db_module.dispose()
    except Exception:
        pass
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Inventory Optimisation Agent API",
        description="Phases 1-3 — Executive Dashboard + Recommendations + Forecasts",
        version="0.3.0",
        lifespan=lifespan,
        # Disable docs in production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        # Q1.1: also allow X-Correlation-Id so the UI/proxy can pass tracing IDs.
        allow_headers=["Authorization", "Content-Type", "X-Correlation-Id", "traceparent"],
        expose_headers=["X-Correlation-Id"],
    )

    # ── Q1.1: correlation-id middleware (no-op when import failed above) ────
    if correlation_id_middleware is not None:
        app.middleware("http")(correlation_id_middleware)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(metrics_router, prefix="/v1/metrics", tags=["metrics"])
    app.include_router(rec_router, prefix="/v1/recommendations", tags=["recommendations"])
    app.include_router(fc_router, prefix="/v1/forecasts", tags=["forecasts"])
    app.include_router(diag_router, prefix="/v1/diagnostics", tags=["diagnostics"])
    app.include_router(sub_router, prefix="/v1/substitutes", tags=["substitutes"])
    # Q2.2: LLM chat + rationale endpoints live under /v1/recommendations so
    # the UI's existing path convention is preserved.
    app.include_router(llm_router, prefix="/v1/recommendations", tags=["chat"])
    # Q2.2+: floating chatbot — works with or without a recId.
    app.include_router(chat_router, prefix="/v1/chat", tags=["chat"])

    # ── Q2.1: agent on-demand trigger ────────────────────────────────────────
    from fastapi import Depends as _Depends
    from app.dependencies import CurrentUser as _CurrentUser, get_current_user as _get_current_user

    @app.post("/v1/agent:run", tags=["agent"], summary="Run the auto-apply agent on demand")
    async def agent_run(_user: _CurrentUser = _Depends(_get_current_user)):
        from app.agent import executor as agent_executor
        res = await agent_executor.run()
        return {
            "evaluated":    res.evaluated,
            "autoApproved": res.auto_approved,
            "autoApplied":  res.auto_applied,
            "skipped":      res.skipped,
            "failed":       res.failed,
            "decisions":    res.decisions,
        }

    # ── Ops endpoints — DLD §7.4 ─────────────────────────────────────────────
    @app.get("/healthz", tags=["ops"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz():
        """Readiness probe: returns 200 only when downstreams are reachable."""
        from app import db as db_module
        checks: dict[str, bool] = {}

        # DB check (optional — readiness still OK without persistence)
        if db_module.is_enabled():
            try:
                from sqlalchemy import text
                async with db_module.session_scope() as s:
                    await s.execute(text("SELECT 1"))
                checks["db"] = True
            except Exception:
                checks["db"] = False
        else:
            checks["db"] = True  # disabled = trivially ready

        # Maximo MIF reachability check (best-effort — don't fail readiness on
        # a transient MAS hiccup; just report it).
        try:
            from app.metrics.maximo_client import fetch_inventory
            mxr = await fetch_inventory(settings)
            checks["maximo"] = mxr is not None
        except Exception:
            checks["maximo"] = False

        ready = all(checks.values())
        return {"ready": ready, "checks": checks}

    # ── Q1.1: Prometheus /metrics (no-op if prometheus_client not installed)
    if settings.prometheus_enabled:
        try:
            from app.observability.metrics import install as install_metrics
            install_metrics(app)
        except Exception as exc:
            logger.warning("Prometheus instrumentation failed: %s", exc)

    return app


app = create_app()
