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
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Load .env HERE, at module import, before any code below reads os.getenv().
load_dotenv()


def _to_asyncpg_url(url: str) -> str:
    """Normalise a Prisma/standard Postgres URL for SQLAlchemy's asyncpg driver.

    1. Normalises the scheme from postgres:// or postgresql:// to postgresql+asyncpg://.
    2. Rewrites ?sslmode=... to ?ssl=... because asyncpg's connect() accepts `ssl`
       rather than `sslmode`. Passing `sslmode` to SQLAlchemy's asyncpg dialect
       causes `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    parsed = urlsplit(url)
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if "sslmode" in qs:
            ssl_val = qs.pop("sslmode")
            if "ssl" not in qs:
                qs["ssl"] = ssl_val
            url = urlunsplit(parsed._replace(query=urlencode(qs, doseq=True)))

    return url


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Paste your Prisma Postgres pooled connection string into .env.")
    return _to_asyncpg_url(url)


# Build the engine with NullPool to prevent open connection leaks across serverless function invokes.
_engine = create_async_engine(
    get_database_url(),
    echo=os.getenv("SQL_ECHO", "").lower() == "true",
    poolclass=NullPool,
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