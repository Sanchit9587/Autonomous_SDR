"""Pydantic <-> ORM conversion. Keeps the two layers decoupled: nothing outside
this file needs to know the storage shape differs from the API shape.

Pattern: to_orm(pydantic) builds a row; to_model(row) rebuilds the Pydantic
object. JSON columns round-trip via model_dump(mode="json") / model_validate.
"""
from __future__ import annotations

from core.db import tables as t
from core.models import (
    AgentDecision,
    Campaign,
    CampaignAsset,
    CampaignProspectLink,
    ConversationTurn,
    Persona,
    Prospect,
    PromptVersion,
)
from core.models.user import User, UserInDB


# --- Campaign ---------------------------------------------------------------
def campaign_to_orm(m: Campaign) -> t.CampaignORM:
    return t.CampaignORM(
        id=m.id, name=m.name, description=m.description, vision_statement=m.vision_statement,
        owner=m.owner, status=m.status.value,
        icp=m.icp.model_dump(mode="json"),
        agent_settings={k: v.model_dump(mode="json") for k, v in m.agent_settings.items()},
        channel_policies=[c.model_dump(mode="json") for c in m.channel_policies],
        default_channel_priority=[c.value for c in m.default_channel_priority],
        budget=m.budget, start_date=m.start_date, end_date=m.end_date,
        target_scale=m.target_scale, pace_per_day=m.pace_per_day, goals=m.goals,
        sources=m.sources, connector_configs=m.connector_configs,
        system_prompt_version=m.system_prompt_version, assigned_rep_ids=m.assigned_rep_ids,
        created_at=m.created_at, updated_at=m.updated_at,
    )


def campaign_to_model(o: t.CampaignORM) -> Campaign:
    return Campaign.model_validate({
        "id": o.id, "name": o.name, "description": o.description, "vision_statement": o.vision_statement,
        "owner": o.owner, "status": o.status,
        "icp": o.icp, "agent_settings": o.agent_settings, "channel_policies": o.channel_policies,
        "default_channel_priority": o.default_channel_priority,
        "budget": o.budget, "start_date": o.start_date, "end_date": o.end_date,
        "target_scale": o.target_scale, "pace_per_day": o.pace_per_day, "goals": o.goals,
        "sources": o.sources or ["apollo", "linkedin"],
        "connector_configs": o.connector_configs or {},
        "system_prompt_version": o.system_prompt_version,
        "assigned_rep_ids": o.assigned_rep_ids, "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- Prospect ---------------------------------------------------------------
def prospect_to_orm(m: Prospect) -> t.ProspectORM:
    return t.ProspectORM(id=m.id, profile=m.profile.model_dump(mode="json"), created_at=m.created_at, updated_at=m.updated_at)


def prospect_to_model(o: t.ProspectORM) -> Prospect:
    return Prospect.model_validate({"id": o.id, "profile": o.profile, "created_at": o.created_at, "updated_at": o.updated_at})


# --- CampaignProspectLink ---------------------------------------------------
def link_to_orm(m: CampaignProspectLink) -> t.CampaignProspectLinkORM:
    return t.CampaignProspectLinkORM(
        id=m.id, campaign_id=m.campaign_id, prospect_id=m.prospect_id, stage=m.stage.value,
        fit_score=m.fit_score, qualification_reasoning=m.qualification_reasoning, persona_id=m.persona_id,
        human_approved=m.human_approved, human_approved_by=m.human_approved_by,
        last_contacted_channel=m.last_contacted_channel, contact_count=m.contact_count,
        follow_up_owed=m.follow_up_owed, next_follow_up_at=m.next_follow_up_at, deal_value=m.deal_value,
        created_at=m.created_at, updated_at=m.updated_at,
    )


def link_to_model(o: t.CampaignProspectLinkORM) -> CampaignProspectLink:
    return CampaignProspectLink.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "prospect_id": o.prospect_id, "stage": o.stage,
        "fit_score": o.fit_score, "qualification_reasoning": o.qualification_reasoning, "persona_id": o.persona_id,
        "human_approved": o.human_approved, "human_approved_by": o.human_approved_by,
        "last_contacted_channel": o.last_contacted_channel, "contact_count": o.contact_count,
        "follow_up_owed": o.follow_up_owed, "next_follow_up_at": o.next_follow_up_at, "deal_value": o.deal_value,
        "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- Persona ----------------------------------------------------------------
def persona_to_orm(m: Persona) -> t.PersonaORM:
    return t.PersonaORM(
        id=m.id, campaign_id=m.campaign_id, name=m.name, description=m.description,
        qualification_notes=m.qualification_notes, importance=m.importance, tone=m.tone.value, tone_notes=m.tone_notes,
        channel_priority=[c.value for c in m.channel_priority],
        templates={k: v.model_dump(mode="json") for k, v in m.templates.items()},
        example_messages=m.example_messages, follow_up_policy=m.follow_up_policy.model_dump(mode="json"),
        created_at=m.created_at, updated_at=m.updated_at,
    )


def persona_to_model(o: t.PersonaORM) -> Persona:
    return Persona.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "name": o.name, "description": o.description,
        "qualification_notes": o.qualification_notes, "importance": o.importance, "tone": o.tone, "tone_notes": o.tone_notes,
        "channel_priority": o.channel_priority, "templates": o.templates, "example_messages": o.example_messages,
        "follow_up_policy": o.follow_up_policy, "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- CampaignAsset ----------------------------------------------------------
def asset_to_orm(m: CampaignAsset) -> t.CampaignAssetORM:
    return t.CampaignAssetORM(
        id=m.id, campaign_id=m.campaign_id, name=m.name, asset_type=m.asset_type.value, url=m.url,
        description=m.description, tags=m.tags, created_at=m.created_at, updated_at=m.updated_at,
    )


def asset_to_model(o: t.CampaignAssetORM) -> CampaignAsset:
    return CampaignAsset.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "name": o.name, "asset_type": o.asset_type, "url": o.url,
        "description": o.description, "tags": o.tags, "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- PromptVersion ----------------------------------------------------------
def prompt_version_to_orm(m: PromptVersion) -> t.PromptVersionORM:
    return t.PromptVersionORM(
        id=m.id, campaign_id=m.campaign_id, agent_name=m.agent_name.value, version_number=m.version_number,
        content=m.content, is_active=m.is_active, created_by=m.created_by, change_note=m.change_note,
        created_at=m.created_at, updated_at=m.updated_at,
    )


def prompt_version_to_model(o: t.PromptVersionORM) -> PromptVersion:
    return PromptVersion.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "agent_name": o.agent_name, "version_number": o.version_number,
        "content": o.content, "is_active": o.is_active, "created_by": o.created_by, "change_note": o.change_note,
        "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- AgentDecision ----------------------------------------------------------
def decision_to_orm(m: AgentDecision) -> t.AgentDecisionORM:
    return t.AgentDecisionORM(
        id=m.id, campaign_id=m.campaign_id, prospect_id=m.prospect_id, agent_name=m.agent_name.value,
        prompt_version_id=m.prompt_version_id, verdict=m.verdict.value, reasoning=m.reasoning,
        confidence=m.confidence, details=m.details, tokens_used=m.tokens_used, model_used=m.model_used,
        latency_ms=m.latency_ms, created_at=m.created_at, updated_at=m.updated_at,
    )


def decision_to_model(o: t.AgentDecisionORM) -> AgentDecision:
    return AgentDecision.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "prospect_id": o.prospect_id, "agent_name": o.agent_name,
        "prompt_version_id": o.prompt_version_id, "verdict": o.verdict, "reasoning": o.reasoning,
        "confidence": o.confidence, "details": o.details, "tokens_used": o.tokens_used, "model_used": o.model_used,
        "latency_ms": o.latency_ms, "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- ConversationTurn -------------------------------------------------------
def turn_to_orm(m: ConversationTurn) -> t.ConversationTurnORM:
    return t.ConversationTurnORM(
        id=m.id, campaign_id=m.campaign_id, prospect_id=m.prospect_id, channel=m.channel.value,
        direction=m.direction.value, content=m.content, agent_name=m.agent_name,
        prompt_version_id=m.prompt_version_id, call_duration_seconds=m.call_duration_seconds,
        transcript_confidence=m.transcript_confidence, created_at=m.created_at, updated_at=m.updated_at,
    )


def turn_to_model(o: t.ConversationTurnORM) -> ConversationTurn:
    return ConversationTurn.model_validate({
        "id": o.id, "campaign_id": o.campaign_id, "prospect_id": o.prospect_id, "channel": o.channel,
        "direction": o.direction, "content": o.content, "agent_name": o.agent_name,
        "prompt_version_id": o.prompt_version_id, "call_duration_seconds": o.call_duration_seconds,
        "transcript_confidence": o.transcript_confidence, "created_at": o.created_at, "updated_at": o.updated_at,
    })


# --- User -------------------------------------------------------------------
def user_to_orm(m: UserInDB) -> t.UserORM:
    return t.UserORM(
        id=m.id, email=m.email.lower(), full_name=m.full_name, title=m.title,
        role=m.role.value, is_active=m.is_active, hashed_password=m.hashed_password,
        created_at=m.created_at, updated_at=m.updated_at,
    )


def user_to_indb(o: t.UserORM) -> UserInDB:
    """Internal — includes the password hash for auth verification."""
    return UserInDB.model_validate({
        "id": o.id, "email": o.email, "full_name": o.full_name, "title": o.title,
        "role": o.role, "is_active": o.is_active, "hashed_password": o.hashed_password,
        "created_at": o.created_at, "updated_at": o.updated_at,
    })


def user_to_model(o: t.UserORM) -> User:
    """Public — no password hash."""
    return User.model_validate({
        "id": o.id, "email": o.email, "full_name": o.full_name, "title": o.title,
        "role": o.role, "is_active": o.is_active,
        "created_at": o.created_at, "updated_at": o.updated_at,
    })