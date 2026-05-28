"""
Alembic environment.

Uses the app's Base.metadata (registered when models_db is imported) so
`alembic revision --autogenerate -m "<msg>"` picks up changes to ORM models.

Reads sqlalchemy.url from the DATABASE_URL env var when present, otherwise
falls back to the value in alembic.ini.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Allow `import app` from the api/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base  # noqa: E402
from app import models_db  # noqa: F401, E402 — register ORM models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

env_url = os.getenv("DATABASE_URL")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
