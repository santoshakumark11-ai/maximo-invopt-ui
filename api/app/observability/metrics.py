"""
Prometheus metrics — DLD §12.1.

Mounts /metrics via prometheus_fastapi_instrumentator and exposes:

    agent_recommendation_total{status,type}
    agent_recommendation_latency_seconds   (histogram)
    agent_writeback_failures_total{target}
    agent_writeback_success_total{target}
    agent_approval_dwell_seconds           (histogram, set when status flips)
    agent_forecast_mape{pattern}           (gauge)
    agent_drift_score{feature}             (gauge)

All instruments degrade to no-ops when prometheus_client is not installed.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator
    _IMPORT_OK = True
except Exception as exc:
    _IMPORT_OK = False
    logger.warning("prometheus_client not available (%s) — /metrics disabled", exc)


# ── Instruments ───────────────────────────────────────────────────────────────

if _IMPORT_OK:
    RECOMMENDATION_TOTAL = Counter(
        "agent_recommendation_total",
        "Recommendations emitted by lifecycle state and type.",
        ["status", "type"],
    )
    RECOMMENDATION_LATENCY = Histogram(
        "agent_recommendation_latency_seconds",
        "End-to-end latency: request received → recommendation persisted.",
    )
    WRITEBACK_FAILURES = Counter(
        "agent_writeback_failures_total", "Writeback failures by target.",
        ["target"],
    )
    WRITEBACK_SUCCESS = Counter(
        "agent_writeback_success_total", "Writeback successes by target.",
        ["target"],
    )
    APPROVAL_DWELL = Histogram(
        "agent_approval_dwell_seconds",
        "Time from NEW → APPROVED (or APPLIED) in seconds.",
        buckets=(60, 300, 900, 3600, 8 * 3600, 24 * 3600, 7 * 24 * 3600),
    )
    FORECAST_MAPE = Gauge(
        "agent_forecast_mape", "WAPE per demand pattern (volume-weighted).",
        ["pattern"],
    )
    DRIFT_SCORE = Gauge(
        "agent_drift_score", "Feature drift score (0..1).", ["feature"],
    )
else:
    RECOMMENDATION_TOTAL = None
    RECOMMENDATION_LATENCY = None
    WRITEBACK_FAILURES = None
    WRITEBACK_SUCCESS = None
    APPROVAL_DWELL = None
    FORECAST_MAPE = None
    DRIFT_SCORE = None


# ── Helpers used elsewhere in the app ────────────────────────────────────────

def inc_recommendation(status: str, type_: str) -> None:
    if RECOMMENDATION_TOTAL is not None:
        RECOMMENDATION_TOTAL.labels(status=status, type=type_).inc()


def observe_recommendation_latency(seconds: float) -> None:
    if RECOMMENDATION_LATENCY is not None:
        RECOMMENDATION_LATENCY.observe(seconds)


def inc_writeback_failure(target: str = "MAXIMO") -> None:
    if WRITEBACK_FAILURES is not None:
        WRITEBACK_FAILURES.labels(target=target).inc()


def inc_writeback_success(target: str = "MAXIMO") -> None:
    if WRITEBACK_SUCCESS is not None:
        WRITEBACK_SUCCESS.labels(target=target).inc()


def observe_approval_dwell(seconds: float) -> None:
    if APPROVAL_DWELL is not None:
        APPROVAL_DWELL.observe(seconds)


def set_forecast_mape(pattern: str, mape: float) -> None:
    if FORECAST_MAPE is not None:
        FORECAST_MAPE.labels(pattern=pattern).set(mape)


def set_drift_score(feature: str, score: float) -> None:
    if DRIFT_SCORE is not None:
        DRIFT_SCORE.labels(feature=feature).set(score)


# ── FastAPI wiring ────────────────────────────────────────────────────────────

def install(app: Any) -> None:
    """Attach the instrumentator + expose /metrics.  No-op if deps missing."""
    if not _IMPORT_OK:
        return
    Instrumentator(
        excluded_handlers=["/healthz", "/readyz", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
