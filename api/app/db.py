"""
Async database engine and session factory.

The default URL uses SQLite for a friction-free dev experience; production
sets DATABASE_URL to a postgresql+asyncpg://... DSN.

Persistence is OPTIONAL.  When `persistence_enabled=False` (or when
SQLAlchemy is not installed at all — see _IMPORT_OK below), every store
silently falls back to its existing in-memory dict implementation so the
pre-Q1 demo path continues to work.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import DeclarativeBase
    _IMPORT_OK = True
except Exception as exc:  # SQLAlchemy not installed yet
    logger.warning(
        "SQLAlchemy not available (%s) — persistence disabled, falling back to in-memory store.",
        exc,
    )
    _IMPORT_OK = False
    AsyncEngine = AsyncSession = async_sessionmaker = create_async_engine = None  # type: ignore[assignment]

    class DeclarativeBase:  # type: ignore[no-redef]
        """Shim so model_db.py can still be imported when SQLAlchemy is absent."""
        pass


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models in app.models_db."""


_engine: "AsyncEngine | None" = None
_SessionLocal: "async_sessionmaker[AsyncSession] | None" = None


def is_enabled() -> bool:
    """Master flag combining import availability + settings toggle."""
    if not _IMPORT_OK:
        return False
    settings = get_settings()
    return settings.persistence_enabled


def get_engine() -> "AsyncEngine | None":
    return _engine


async def init_db(settings: Settings | None = None) -> bool:
    """
    Initialise the engine + session factory, then ensure tables exist.
    Returns True on success, False if persistence is disabled or unavailable.

    Tables are created with `create_all` against the bound metadata for the
    SQLite dev path; Alembic owns schema management in production (run
    `alembic upgrade head` from the api/ directory).
    """
    global _engine, _SessionLocal

    if not _IMPORT_OK:
        return False

    settings = settings or get_settings()
    if not settings.persistence_enabled:
        logger.info("Persistence disabled by settings.persistence_enabled=False")
        return False

    url = settings.database_url
    # SQLAlchemy emits noisy logs on INFO; keep it at WARNING by default.
    _engine = create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    _SessionLocal = async_sessionmaker(
        _engine, expire_on_commit=False, class_=AsyncSession
    )

    # Import here to register tables on Base.metadata before create_all.
    from app import models_db  # noqa: F401

    try:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("DB schema bootstrap failed: %s — disabling persistence", exc)
        _engine = None
        _SessionLocal = None
        return False

    logger.info("DB engine initialised against %s", _mask_url(url))
    return True


async def dispose() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _SessionLocal = None


@asynccontextmanager
async def session_scope() -> AsyncIterator["AsyncSession"]:
    """
    Yield a transactional session.  Callers MUST use `async with`:

        async with session_scope() as s:
            ...

    Commits on clean exit; rolls back on exception.
    """
    if _SessionLocal is None:
        raise RuntimeError(
            "DB session requested but persistence is disabled. "
            "Check db.is_enabled() before calling session_scope()."
        )
    session: AsyncSession = _SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def _mask_url(url: str) -> str:
    """Mask the password component of a DB URL for safe logging."""
    if "@" not in url or "://" not in url:
        return url
    proto, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{proto}://{user}:***@{host}"
    return url
