"""
Structured logging setup.

Configures the root logger as either:
    - JSON formatter via python_json_logger.JsonFormatter (production)
    - Human-readable formatter (dev)

Adds a correlation_id middleware that:
    - Reads X-Correlation-Id from the request header (or generates one)
    - Stores it in a contextvar so log lines emitted during the request carry it
    - Echoes it back as a response header so the client can join logs
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Any

from app.config import get_settings

# Context variable holding the current request's correlation ID.
correlation_id_var: "contextvars.ContextVar[str]" = contextvars.ContextVar(
    "correlation_id", default="-"
)


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    # Don't double-configure if uvicorn already attached handlers.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.addFilter(_CorrelationFilter())

    if settings.log_json:
        try:
            from pythonjsonlogger import jsonlogger
            formatter: Any = jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            )
        except Exception:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] cid=%(correlation_id)s %(name)s: %(message)s"
            )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] cid=%(correlation_id)s %(name)s: %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)


# ── FastAPI middleware ────────────────────────────────────────────────────────

async def correlation_id_middleware(request, call_next):  # type: ignore[no-untyped-def]
    incoming = request.headers.get("x-correlation-id") or request.headers.get("traceparent")
    cid = incoming or str(uuid.uuid4())
    token = correlation_id_var.set(cid)
    try:
        response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        return response
    finally:
        correlation_id_var.reset(token)
