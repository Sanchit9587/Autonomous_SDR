"""FastAPI application entrypoint.

Run locally (from backend/):
    uvicorn api.main:app --reload

Tables are managed by Alembic (`alembic upgrade head`), not created here — so a
fresh clone runs migrations once, and the app never silently diverges from the
migration history. The startup hook only verifies connectivity.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import text

from core.db.engine import get_engine
from auth.router import router as auth_router
from orchestrator.api import router as campaigns_router
from orchestrator.scheduler import shutdown_scheduler, start_scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on startup if the DB is unreachable, with a clear message.
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not connect to the database on startup: {exc}. "
            "Check DATABASE_URL in .env and that migrations have been run (alembic upgrade head)."
        ) from exc
    start_scheduler()      # follow-up timers (persistent job store on Postgres)
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title="Autonomous SDR Platform", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(campaigns_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}