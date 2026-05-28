# syntax=docker/dockerfile:1.7
#
# Inventory Optimisation Agent — API image (production)
#
# Python 3.12 chosen for the production image because it has wheels for every
# dep in requirements.txt (numpy 2.1+, scipy 1.14+, statsforecast 1.7+, numba).
# Python 3.13 also works but skips statsforecast (forecasting falls back to
# the NumPy bootstrap quantile path).
#
# OpenShift compatibility:
#   - Runs as USER 1001, but file permissions are also set for group 0 (root)
#     so OpenShift's arbitrary-UID security context (always in group 0) can
#     read and write app files.
#   - Listens on 8080 (unprivileged port).
#   - HEALTHCHECK uses /healthz, which the FastAPI app exposes.

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Build tools are only needed for any source-built wheels.  Most Q1/Q2 deps
# now ship Python 3.12 binary wheels so this stays tiny.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    PORT=8080

# Minimal runtime deps — curl is used by the HEALTHCHECK only.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user, but group 0 ownership for OpenShift arbitrary UID compatibility.
RUN useradd --create-home --home-dir /app --shell /sbin/nologin --uid 1001 appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/      ./app/
COPY alembic/  ./alembic/
COPY alembic.ini ./

# OpenShift random-UID safe: make everything readable + executable by group 0
# and writable for paths the app needs (SQLite file fallback, log buffering).
RUN chgrp -R 0 /app \
 && chmod -R g=u /app \
 && mkdir -p /app/data \
 && chmod -R g=u /app/data

USER 1001

EXPOSE 8080

# /healthz returns 200 once the FastAPI app is up.  Curl with --fail so a 5xx
# correctly marks the container unhealthy.
HEALTHCHECK --interval=20s --timeout=3s --start-period=15s --retries=3 \
  CMD curl --fail --silent http://localhost:8080/healthz || exit 1

# Two workers is a sensible floor for the demo profile (DLD §15.2).  Scale by
# bumping the Deployment replica count, not by adding more uvicorn workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
