"""Repository layer: every DB access the orchestrator needs, as async functions
that take a session and return Pydantic models (never ORM rows — those stay
inside this package). This is what replaces the in-memory dicts in api.py.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import mappers as mp
from core.db import tables as t
from core.models import (
    AgentDecision,
    Campaign,
    CampaignAsset,
    CampaignProspectLink,
    ConversationTurn,
    Persona,
    Prospect,
)


# --- campaigns --------------------------------------------------------------
async def save_campaign(session: AsyncSession, campaign: Campaign) -> Campaign:
    await session.merge(mp.campaign_to_orm(campaign))
    return campaign


async def get_campaign(session: AsyncSession, campaign_id: str) -> Optional[Campaign]:
    row = await session.get(t.CampaignORM, campaign_id)
    return mp.campaign_to_model(row) if row else None


async def list_campaigns(session: AsyncSession) -> list[Campaign]:
    rows = (await session.execute(select(t.CampaignORM))).scalars().all()
    return [mp.campaign_to_model(r) for r in rows]


# --- prospects + links ------------------------------------------------------
async def save_prospect(session: AsyncSession, prospect: Prospect) -> Prospect:
    await session.merge(mp.prospect_to_orm(prospect))
    return prospect


async def get_prospect(session: AsyncSession, prospect_id: str) -> Optional[Prospect]:
    row = await session.get(t.ProspectORM, prospect_id)
    return mp.prospect_to_model(row) if row else None


async def list_prospects(session: AsyncSession) -> list[Prospect]:
    rows = (await session.execute(select(t.ProspectORM))).scalars().all()
    return [mp.prospect_to_model(r) for r in rows]


async def save_link(session: AsyncSession, link: CampaignProspectLink) -> CampaignProspectLink:
    await session.merge(mp.link_to_orm(link))
    return link


async def get_link(session: AsyncSession, link_id: str) -> Optional[CampaignProspectLink]:
    row = await session.get(t.CampaignProspectLinkORM, link_id)
    return mp.link_to_model(row) if row else None


async def list_links_for_campaign(session: AsyncSession, campaign_id: str) -> list[CampaignProspectLink]:
    rows = (await session.execute(
        select(t.CampaignProspectLinkORM).where(t.CampaignProspectLinkORM.campaign_id == campaign_id)
    )).scalars().all()
    return [mp.link_to_model(r) for r in rows]


async def list_all_links(session: AsyncSession) -> list[CampaignProspectLink]:
    rows = (await session.execute(select(t.CampaignProspectLinkORM))).scalars().all()
    return [mp.link_to_model(r) for r in rows]


async def list_owed_follow_up_links(session: AsyncSession, campaign_id: str) -> list[CampaignProspectLink]:
    """Links whose follow-up fired while the campaign was paused (owed on resume)."""
    rows = (await session.execute(
        select(t.CampaignProspectLinkORM).where(
            t.CampaignProspectLinkORM.campaign_id == campaign_id,
            t.CampaignProspectLinkORM.follow_up_owed == True,  # noqa: E712
        )
    )).scalars().all()
    return [mp.link_to_model(r) for r in rows]


# --- personas ---------------------------------------------------------------
async def save_persona(session: AsyncSession, persona: Persona) -> Persona:
    await session.merge(mp.persona_to_orm(persona))
    return persona


async def list_personas_for_campaign(session: AsyncSession, campaign_id: str) -> list[Persona]:
    rows = (await session.execute(
        select(t.PersonaORM).where(t.PersonaORM.campaign_id == campaign_id)
    )).scalars().all()
    return [mp.persona_to_model(r) for r in rows]


# --- assets -----------------------------------------------------------------
async def save_asset(session: AsyncSession, asset: CampaignAsset) -> CampaignAsset:
    await session.merge(mp.asset_to_orm(asset))
    return asset


async def list_assets_for_campaign(session: AsyncSession, campaign_id: str) -> list[CampaignAsset]:
    rows = (await session.execute(
        select(t.CampaignAssetORM).where(t.CampaignAssetORM.campaign_id == campaign_id)
    )).scalars().all()
    return [mp.asset_to_model(r) for r in rows]


# --- decisions --------------------------------------------------------------
async def append_decision(session: AsyncSession, decision: AgentDecision) -> AgentDecision:
    session.add(mp.decision_to_orm(decision))
    return decision


async def list_decisions_for_prospect(session: AsyncSession, campaign_id: str, prospect_id: str) -> list[AgentDecision]:
    rows = (await session.execute(
        select(t.AgentDecisionORM)
        .where(t.AgentDecisionORM.campaign_id == campaign_id, t.AgentDecisionORM.prospect_id == prospect_id)
        .order_by(t.AgentDecisionORM.created_at)
    )).scalars().all()
    return [mp.decision_to_model(r) for r in rows]


# --- conversation turns -----------------------------------------------------
async def append_turn(session: AsyncSession, turn: ConversationTurn) -> ConversationTurn:
    session.add(mp.turn_to_orm(turn))
    return turn


async def list_turns_for_prospect(session: AsyncSession, campaign_id: str, prospect_id: str) -> list[ConversationTurn]:
    rows = (await session.execute(
        select(t.ConversationTurnORM)
        .where(t.ConversationTurnORM.campaign_id == campaign_id, t.ConversationTurnORM.prospect_id == prospect_id)
        .order_by(t.ConversationTurnORM.created_at)
    )).scalars().all()
    return [mp.turn_to_model(r) for r in rows]


async def count_touches_today(session: AsyncSession, campaign_id: str) -> tuple[int, dict[str, int]]:
    """Count today's OUTBOUND conversation turns for a campaign (= sent touches),
    returning (total, per-channel). This is the source of truth for pace and
    per-channel daily limits — derived from real sent turns, not a separate
    counter that could drift."""
    from datetime import datetime, timezone
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (await session.execute(
        select(t.ConversationTurnORM.channel).where(
            t.ConversationTurnORM.campaign_id == campaign_id,
            t.ConversationTurnORM.direction == "outbound",
            t.ConversationTurnORM.created_at >= start_of_day,
        )
    )).scalars().all()
    per_channel: dict[str, int] = {}
    for ch in rows:
        per_channel[ch] = per_channel.get(ch, 0) + 1
    return len(rows), per_channel


# --- suppression ------------------------------------------------------------
async def add_suppression(session: AsyncSession, key: str) -> None:
    await session.merge(t.SuppressionEntryORM(key=key.strip().lower()))


async def list_suppression(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(t.SuppressionEntryORM.key))).scalars().all()
    return sorted(rows)


async def is_suppressed(session: AsyncSession, key: str) -> bool:
    row = await session.get(t.SuppressionEntryORM, key.strip().lower())
    return row is not None


# --- users ------------------------------------------------------------------
async def save_user(session: AsyncSession, user) -> None:
    """Accepts a UserInDB (carries the hash)."""
    from core.db import mappers as _mp
    await session.merge(_mp.user_to_orm(user))


async def get_user_by_email(session: AsyncSession, email: str):
    """Returns UserInDB (with hash) for auth, or None."""
    from core.db import mappers as _mp
    row = (await session.execute(
        select(t.UserORM).where(t.UserORM.email == email.strip().lower())
    )).scalar_one_or_none()
    return _mp.user_to_indb(row) if row else None


async def get_user(session: AsyncSession, user_id: str):
    """Returns public User (no hash), or None."""
    from core.db import mappers as _mp
    row = await session.get(t.UserORM, user_id)
    return _mp.user_to_model(row) if row else None


async def list_users(session: AsyncSession):
    from core.db import mappers as _mp
    rows = (await session.execute(select(t.UserORM))).scalars().all()
    return [_mp.user_to_model(r) for r in rows]


async def filter_existing_user_ids(session: AsyncSession, ids: list[str]) -> tuple[list[str], list[str]]:
    """Split ids into (valid, invalid) by which ones are real users. Used to keep
    junk (e.g. the OpenAPI placeholder 'string', or ids from a stale/other DB)
    out of assigned_rep_ids."""
    if not ids:
        return [], []
    rows = (await session.execute(
        select(t.UserORM.id).where(t.UserORM.id.in_(ids))
    )).scalars().all()
    existing = set(rows)
    # Preserve order, dedupe.
    valid, invalid, seen = [], [], set()
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        (valid if i in existing else invalid).append(i)
    return valid, invalid


# --- rep-facing read queries -------------------------------------------------
async def list_recent_decisions(session: AsyncSession, campaign_id: Optional[str] = None, limit: int = 50) -> list[AgentDecision]:
    """Chronological (newest-first) agent decisions — powers the Live Activity feed.
    Optionally scoped to one campaign."""
    q = select(t.AgentDecisionORM).order_by(t.AgentDecisionORM.created_at.desc()).limit(limit)
    if campaign_id:
        q = q.where(t.AgentDecisionORM.campaign_id == campaign_id)
    from core.db import mappers as _mp
    rows = (await session.execute(q)).scalars().all()
    return [_mp.decision_to_model(r) for r in rows]


async def list_escalations(session: AsyncSession, campaign_id: Optional[str] = None, limit: int = 100) -> list[AgentDecision]:
    """Decisions where an agent escalated to a human — the Escalations queue."""
    q = (select(t.AgentDecisionORM)
         .where(t.AgentDecisionORM.verdict == "escalate")
         .order_by(t.AgentDecisionORM.created_at.desc()).limit(limit))
    if campaign_id:
        q = q.where(t.AgentDecisionORM.campaign_id == campaign_id)
    from core.db import mappers as _mp
    rows = (await session.execute(q)).scalars().all()
    return [_mp.decision_to_model(r) for r in rows]


async def list_prospects_for_campaign(session: AsyncSession, campaign_id: str) -> list[tuple[CampaignProspectLink, Prospect]]:
    """Every prospect in a campaign, paired with its funnel link — for the
    Prospects list. Joins links to prospects in one query."""
    from core.db import mappers as _mp
    rows = (await session.execute(
        select(t.CampaignProspectLinkORM, t.ProspectORM)
        .join(t.ProspectORM, t.CampaignProspectLinkORM.prospect_id == t.ProspectORM.id)
        .where(t.CampaignProspectLinkORM.campaign_id == campaign_id)
        .order_by(t.CampaignProspectLinkORM.created_at.desc())
    )).all()
    return [(_mp.link_to_model(link), _mp.prospect_to_model(pros)) for link, pros in rows]


async def get_prospect_for_link(session: AsyncSession, link: CampaignProspectLink) -> Optional[Prospect]:
    return await get_prospect(session, link.prospect_id)


async def existing_dedupe_keys_for_campaign(session: AsyncSession, campaign_id: str) -> set[str]:
    """Dedupe keys (linkedin_url / work_email / name, lowercased) of prospects
    already in a campaign — used to skip duplicates on CSV import."""
    pairs = await list_prospects_for_campaign(session, campaign_id)
    return {prospect.dedupe_key() for _link, prospect in pairs}