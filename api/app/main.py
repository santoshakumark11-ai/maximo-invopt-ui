"""
Inventory Optimisation Agent — Phase 1 API
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.auth.router import router as auth_router
from app.metrics.router import router as metrics_router

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
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Inventory Optimisation Agent API",
        description="Phase 1 — Executive Dashboard metrics backed by Maximo MIF",
        version="0.1.0",
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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(metrics_router, prefix="/v1/metrics", tags=["metrics"])

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/healthz", tags=["ops"])
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
