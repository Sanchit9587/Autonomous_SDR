"""Async SQLAlchemy engine + session setup, pointed at Prisma Postgres.

Prisma gives you two standard strings:
  DATABASE_URL  -> pooled  (runtime app queries)
  DIRECT_URL    -> direct  (migrations / batch)

Paste them in as-is (postgres:// or postgresql://). This module rewrites the
scheme to postgresql+asyncpg:// for the async driver and normalises the
sslmode param that asyncpg needs, so you don't have to hand-edit the strings.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _to_asyncpg_url(url: str) -> str:
    """Normalise a Prisma/standard Postgres URL for SQLAlchemy's asyncpg driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    # asyncpg does not accept ?sslmode=; it takes ssl=... instead. Prisma requires
    # SSL, so translate sslmode=require -> ssl=true and drop the unsupported param.
    if "sslmode=require" in url:
        url = url.replace("sslmode=require", "ssl=true")
    return url


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Paste your Prisma Postgres pooled connection string into .env.")
    return _to_asyncpg_url(url)


# echo=True in dev to see SQL; pool_pre_ping avoids stale-connection errors on
# the pooled Prisma endpoint after idle periods.
_engine = create_async_engine(
    get_database_url() if os.getenv("DATABASE_URL") else "postgresql+asyncpg://placeholder",
    echo=os.getenv("SQL_ECHO", "").lower() == "true",
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session, commits on success, rolls back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine():
    return _engine