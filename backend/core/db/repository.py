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


# --- suppression ------------------------------------------------------------
async def add_suppression(session: AsyncSession, key: str) -> None:
    await session.merge(t.SuppressionEntryORM(key=key.strip().lower()))


async def list_suppression(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(t.SuppressionEntryORM.key))).scalars().all()
    return sorted(rows)


async def is_suppressed(session: AsyncSession, key: str) -> bool:
    row = await session.get(t.SuppressionEntryORM, key.strip().lower())
    return row is not None