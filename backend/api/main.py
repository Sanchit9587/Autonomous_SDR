"""FastAPI application entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.db.engine import get_engine
from auth.router import router as auth_router
from orchestrator.api import router as campaigns_router
from orchestrator.rep_api import router as rep_router
from orchestrator.scheduler import shutdown_scheduler, start_scheduler

load_dotenv()

# Vercel is serverless — a long-lived background scheduler can't run there, so
# it's only started in a normal (always-on) process.
IS_VERCEL = os.getenv("VERCEL") == "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not connect to the database on startup: {exc}. "
            "Check DATABASE_URL in .env and that migrations have been run (alembic upgrade head)."
        ) from exc

    if not IS_VERCEL:
        start_scheduler()  # follow-up timers (persistent Postgres job store)

    try:
        yield
    finally:
        if not IS_VERCEL:
            shutdown_scheduler()


app = FastAPI(
    title="Autonomous SDR Platform",
    lifespan=lifespan,
    redirect_slashes=False,  # Prevents 307 redirects on preflight OPTIONS requests
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://autonomous-sdr-94rm.vercel.app",  # Your primary frontend deployment
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # Handles dynamic Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(campaigns_router)
app.include_router(rep_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}