"""Alembic migration environment.

Migrations run on a SYNC driver (psycopg2) against Prisma's DIRECT_URL (the
non-pooled connection Prisma recommends for migrations/batch). Runtime app
queries use asyncpg + the pooled DATABASE_URL; migrations are a separate,
short-lived process so a sync driver here keeps Alembic simple.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from core.db.tables import Base

# Alembic does not read .env on its own (unlike the app, which uses python-dotenv).
# Load it here so DIRECT_URL / DATABASE_URL are visible to _migration_url().
# Looks for .env in the current working dir (run alembic from backend/).
load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migration_url() -> str:
    # Prefer DIRECT_URL (non-pooled) for migrations; fall back to DATABASE_URL.
    url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DIRECT_URL (preferred) or DATABASE_URL for migrations.")
    # Sync driver for Alembic: normalise to postgresql+psycopg2://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def run_migrations_offline() -> None:
    context.configure(url=_migration_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _migration_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()