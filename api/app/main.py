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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Inventory Optimisation API")
    logger.info("Maximo base URL: %s", settings.maximo_base_url)
    logger.info("Environment: %s", settings.app_env)

    # Seed recommendations from live Maximo inventory on startup.
    #
    # Behaviour matrix:
    #   Maximo reachable, records returned  → seed_from_live_data() clears store
    #                                         and populates with live results
    #                                         (even if 0 qualify — no fake data)
    #   Maximo reachable, 0 records         → seed_from_live_data() clears store
    #   Maximo unreachable / exception      → leave hardcoded seed intact
    try:
        from app.metrics.maximo_client import fetch_inventory
        from app.recommendations import store as rec_store
        records = await fetch_inventory(settings)
        # fetch_inventory returns [] both on error (logged as warning) and on
        # genuine empty result.  Only skip seeding when it returned nothing —
        # the warning in maximo_client tells us why.
        if records:
            n = rec_store.seed_from_live_data(records)
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

    yield
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
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(metrics_router, prefix="/v1/metrics", tags=["metrics"])
    app.include_router(rec_router, prefix="/v1/recommendations", tags=["recommendations"])
    app.include_router(fc_router, prefix="/v1/forecasts", tags=["forecasts"])

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/healthz", tags=["ops"])
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
