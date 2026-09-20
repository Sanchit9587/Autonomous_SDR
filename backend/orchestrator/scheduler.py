"""APScheduler-based follow-up scheduler.

Design (as agreed):
  * Timers keep running through a pause; only ACTION is gated on campaign status.
  * A follow-up that fires while paused parks itself (follow_up_owed) and fires
    on resume — immediately if within working hours, else next window.
  * A follow-up that still had time left when paused just fires normally later
    (the clock never stopped), needing no special handling.
  * Jobs live in a persistent SQLAlchemy job store on Postgres, so they survive
    an app restart.

Only the follow-up job type is built — deferred SENDS are intentionally omitted
until a messaging connector exists (a job firing into a nonexistent connector
would be dead code). Adding them later is one new callback here.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.db.engine import SessionLocal
from core.models import Campaign, Persona
from orchestrator import service

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def _sync_jobstore_url() -> str:
    """APScheduler's SQLAlchemy jobstore is synchronous, so it needs a sync driver
    (psycopg2), not asyncpg. Reuse DIRECT_URL (same one Alembic uses)."""
    url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL") or ""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    # psycopg2 accepts sslmode in the URL directly (unlike asyncpg), so leave it.
    return url


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {"default": SQLAlchemyJobStore(url=_sync_jobstore_url())}
        _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    return _scheduler


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Follow-up scheduler started")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Follow-up scheduler stopped")


# --- working-hours helpers (mirror the Personalize channel_selector rule) ----
def _parse_working_hours(working_hours: Optional[str]) -> Optional[tuple[time, time]]:
    if not working_hours:
        return None
    try:
        window = working_hours.split()[0]
        start_s, end_s = window.split("-")
        sh, sm_ = map(int, start_s.split(":"))
        eh, em = map(int, end_s.split(":"))
        return time(sh, sm_), time(eh, em)
    except Exception:
        return None


def _campaign_working_hours(campaign: Campaign) -> Optional[tuple[time, time]]:
    """Use the first channel policy that defines working hours (campaign-wide
    approximation; per-channel refinement happens in Personalize on the loop-back)."""
    for policy in campaign.channel_policies:
        hrs = _parse_working_hours(policy.working_hours)
        if hrs:
            return hrs
    return None


def compute_fire_time(campaign: Campaign, *, base: Optional[datetime] = None, delay_days: int = 0) -> datetime:
    """When should a follow-up actually fire: base + delay, then pushed to the
    next working-hours window if it lands outside one."""
    now = base or datetime.now(timezone.utc)
    target = now + timedelta(days=delay_days)
    hours = _campaign_working_hours(campaign)
    if hours is None:
        return target
    start, end = hours
    if start <= target.time() <= end:
        return target
    # Outside hours -> next window start (today if still upcoming, else tomorrow).
    candidate = target.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    if candidate <= target:
        candidate = candidate + timedelta(days=1)
    return candidate


# --- job management ----------------------------------------------------------
def _job_id(campaign_id: str, link_id: str) -> str:
    return f"followup:{campaign_id}:{link_id}"


def schedule_follow_up(campaign: Campaign, link_id: str, *, delay_days: int, base: Optional[datetime] = None) -> str:
    """Schedule (or reschedule) a follow-up for one prospect. Working-hours aware."""
    sched = get_scheduler()
    fire_at = compute_fire_time(campaign, base=base, delay_days=delay_days)
    job_id = _job_id(campaign.id, link_id)
    sched.add_job(
        _run_follow_up_job, trigger="date", run_date=fire_at,
        args=[campaign.id, link_id], id=job_id, replace_existing=True, misfire_grace_time=3600,
    )
    logger.info("Scheduled follow-up %s at %s", job_id, fire_at.isoformat())
    return fire_at.isoformat()


def cancel_follow_ups_for_campaign(campaign_id: str) -> int:
    """Remove all pending follow-up jobs for a campaign (used on archive/complete)."""
    sched = get_scheduler()
    removed = 0
    for job in sched.get_jobs():
        if job.id.startswith(f"followup:{campaign_id}:"):
            job.remove()
            removed += 1
    return removed


# --- the job callback --------------------------------------------------------
def _run_follow_up_job(campaign_id: str, link_id: str) -> None:
    """APScheduler calls this synchronously; bridge into async service code.

    A fresh event loop per fire keeps this independent of the app's loop (the
    scheduler may run in the same process, but the job must own its DB session
    lifecycle cleanly)."""
    asyncio.run(_run_follow_up_async(campaign_id, link_id))


async def _run_follow_up_async(campaign_id: str, link_id: str) -> None:
    async with SessionLocal() as session:
        try:
            result = await service.fire_follow_up(session, campaign_id, link_id)
            await session.commit()
            logger.info("Follow-up job %s:%s -> %s", campaign_id, link_id, result.get("status"))
        except Exception:  # noqa: BLE001
            await session.rollback()
            logger.exception("Follow-up job %s:%s failed", campaign_id, link_id)


# --- resume hook -------------------------------------------------------------
async def fire_owed_follow_ups(session, campaign: Campaign) -> int:
    """On campaign resume: every prospect whose follow-up fired while paused is
    'owed'. Reschedule each to fire now (or next working window). Returns count."""
    from core.db import repository as repo

    owed = await repo.list_owed_follow_up_links(session, campaign.id)
    for link in owed:
        # delay_days=0 => now, then working-hours-adjusted by compute_fire_time.
        fire_at = schedule_follow_up(campaign, link.id, delay_days=0)
        link.next_follow_up_at = fire_at
        # leave follow_up_owed=True until the job actually fires and clears it,
        # so a crash between here and fire doesn't lose the obligation.
        await repo.save_link(session, link)
    logger.info("Re-armed %d owed follow-ups for campaign %s", len(owed), campaign.id)
    return len(owed)