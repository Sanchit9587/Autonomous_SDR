"""FastAPI router for campaign + prospect control, backed by the database.

Every endpoint takes an async DB session and reads/writes via core.db.repository
(agents decide, orchestrator executes — and now persists). The only remaining
in-memory piece is the global kill switch: it's a platform-wide emergency stop
whose "off on restart" behaviour is acceptable (a restart is itself a reset),
and it isn't one of the persisted domain objects.

Agents are synchronous and fast (rule/RAG/one optional LLM call), so they're
called directly inside the async endpoints. If an agent's LLM call ever becomes
slow enough to block the event loop under load, wrap agent.run() in
fastapi.concurrency.run_in_threadpool — the call sites are all marked below.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import AgentContext
from agents.personalize.agent import PersonalizeAgent
from agents.research.agent import ResearchAgent
from auth.dependencies import require_manager
from core.db import repository as repo
from core.db.engine import get_session
from core.models import (
    AgentDecision,
    AgentSettings,
    Campaign,
    CampaignAsset,
    CampaignProspectLink,
    Channel,
    ChannelPolicy,
    ConversationTurn,
    DecisionVerdict,
    Direction,
    FunnelStage,
    ICPFilter,
    Persona,
    Prospect,
)
from orchestrator import campaign_controller as cc
from orchestrator import scheduler as sched
from orchestrator import service
from orchestrator import state_machine as sm
from orchestrator.conflict_resolver import detect_cross_campaign_conflicts, find_duplicate_prospects

# The entire /campaigns API is the Manager control plane, so the whole router
# requires an authenticated Manager (Admin passes too). Rep-facing read views
# will live in a separate rep router with rep-scoped queries.
router = APIRouter(prefix="/campaigns", tags=["campaigns"], dependencies=[Depends(require_manager)])

# Stateless agent instances (no per-request state; safe to share).
research_agent = ResearchAgent()

# Global kill switch — deliberately in-memory (see module docstring).
kill_switch = cc.GlobalKillSwitch()


# --- request/response payloads ---------------------------------------------
class CreateCampaignRequest(BaseModel):
    name: str
    owner: str
    description: Optional[str] = None
    vision_statement: Optional[str] = None
    icp: ICPFilter = ICPFilter()
    agent_settings: dict[str, AgentSettings] = {}
    default_channel_priority: list = []
    channel_policies: list[ChannelPolicy] = []
    budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_scale: Optional[int] = None
    pace_per_day: Optional[int] = None
    goals: list[str] = []


class UpdateCampaignRequest(BaseModel):
    """All optional — only provided fields are updated (PATCH semantics)."""
    name: Optional[str] = None
    description: Optional[str] = None
    vision_statement: Optional[str] = None
    icp: Optional[ICPFilter] = None
    agent_settings: Optional[dict[str, AgentSettings]] = None
    default_channel_priority: Optional[list] = None
    channel_policies: Optional[list[ChannelPolicy]] = None
    budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_scale: Optional[int] = None
    pace_per_day: Optional[int] = None
    goals: Optional[list[str]] = None
    assigned_rep_ids: Optional[list[str]] = None


class TransitionRequest(BaseModel):
    to_stage: FunnelStage
    reason: Optional[str] = None


class ConverseRequest(BaseModel):
    inbound_message: Optional[str] = None
    trigger: str = "reply"                 # "reply" | "follow_up"
    channel: Channel = Channel.EMAIL


# --- helpers ----------------------------------------------------------------
async def _require_campaign(session: AsyncSession, campaign_id: str) -> Campaign:
    campaign = await repo.get_campaign(session, campaign_id)
    if campaign is None:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    return campaign


async def _require_link(session: AsyncSession, link_id: str) -> CampaignProspectLink:
    link = await repo.get_link(session, link_id)
    if link is None:
        raise HTTPException(404, f"CampaignProspectLink {link_id} not found")
    return link


async def _require_prospect(session: AsyncSession, prospect_id: str) -> Prospect:
    prospect = await repo.get_prospect(session, prospect_id)
    if prospect is None:
        raise HTTPException(404, f"Prospect {prospect_id} not found")
    return prospect


# --- campaign lifecycle ------------------------------------------------------
@router.post("", response_model=Campaign)
async def create_campaign(body: CreateCampaignRequest, session: AsyncSession = Depends(get_session)) -> Campaign:
    campaign = Campaign(**body.model_dump())
    return await repo.save_campaign(session, campaign)


@router.get("", response_model=list[Campaign])
async def list_campaigns(session: AsyncSession = Depends(get_session)) -> list[Campaign]:
    return await repo.list_campaigns(session)


@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    return await _require_campaign(session, campaign_id)


@router.patch("/{campaign_id}", response_model=Campaign)
async def update_campaign(campaign_id: str, body: UpdateCampaignRequest, session: AsyncSession = Depends(get_session)) -> Campaign:
    """Edit campaign config (Campaign Config / Modify screens). Only provided
    fields change; the rest are left as-is."""
    campaign = await _require_campaign(session, campaign_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(campaign, field, value)
    return await repo.save_campaign(session, campaign)


async def _lifecycle_endpoint(session: AsyncSession, campaign_id: str, action) -> Campaign:
    campaign = await _require_campaign(session, campaign_id)
    try:
        action(campaign)
    except cc.InvalidCampaignStatusTransitionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await repo.save_campaign(session, campaign)


@router.post("/{campaign_id}/activate", response_model=Campaign)
async def activate_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    return await _lifecycle_endpoint(session, campaign_id, cc.activate)


@router.post("/{campaign_id}/pause", response_model=Campaign)
async def pause_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    """Pausing one campaign never touches any other."""
    return await _lifecycle_endpoint(session, campaign_id, cc.pause)


@router.post("/{campaign_id}/resume", response_model=Campaign)
async def resume_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    campaign = await _lifecycle_endpoint(session, campaign_id, cc.resume)
    # Fire any follow-ups that came due while the campaign was paused.
    await sched.fire_owed_follow_ups(session, campaign)
    return campaign


@router.post("/{campaign_id}/complete", response_model=Campaign)
async def complete_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    campaign = await _lifecycle_endpoint(session, campaign_id, cc.complete)
    sched.cancel_follow_ups_for_campaign(campaign_id)  # terminal: clean up timers
    return campaign


@router.post("/{campaign_id}/archive", response_model=Campaign)
async def archive_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    campaign = await _lifecycle_endpoint(session, campaign_id, cc.archive)
    sched.cancel_follow_ups_for_campaign(campaign_id)  # terminal: clean up timers
    return campaign


@router.post("/{campaign_id}/duplicate", response_model=Campaign)
async def duplicate_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    original = await _require_campaign(session, campaign_id)
    clone = cc.duplicate(original)
    return await repo.save_campaign(session, clone)


@router.post("/kill-switch/engage")
async def engage_kill_switch() -> dict[str, bool]:
    kill_switch.engage()
    return {"engaged": True}


@router.post("/kill-switch/disengage")
async def disengage_kill_switch() -> dict[str, bool]:
    kill_switch.disengage()
    return {"engaged": False}


# --- prospects + funnel transitions -----------------------------------------
@router.post("/{campaign_id}/prospects", response_model=CampaignProspectLink)
async def add_prospect(campaign_id: str, prospect: Prospect, session: AsyncSession = Depends(get_session)) -> CampaignProspectLink:
    await _require_campaign(session, campaign_id)
    await repo.save_prospect(session, prospect)
    link = CampaignProspectLink(campaign_id=campaign_id, prospect_id=prospect.id)
    return await repo.save_link(session, link)


@router.get("/{campaign_id}/funnel")
async def get_funnel(campaign_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    await _require_campaign(session, campaign_id)
    links = await repo.list_links_for_campaign(session, campaign_id)
    return sm.funnel_counts(links)


@router.post("/{campaign_id}/prospects/{link_id}/transition", response_model=CampaignProspectLink)
async def transition_prospect(campaign_id: str, link_id: str, body: TransitionRequest, session: AsyncSession = Depends(get_session)) -> CampaignProspectLink:
    campaign = await _require_campaign(session, campaign_id)
    link = await _require_link(session, link_id)

    if kill_switch.is_engaged and body.to_stage in sm._OUTREACH_STAGES:
        raise HTTPException(423, "Global kill switch is engaged — no autonomous outreach permitted")

    try:
        sm.transition(link, body.to_stage, campaign, reason=body.reason)
    except sm.InvalidTransitionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except sm.CampaignNotLiveError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await repo.save_link(session, link)


@router.get("/conflicts/duplicates")
async def get_duplicate_prospects(session: AsyncSession = Depends(get_session)) -> list[dict]:
    dupes = find_duplicate_prospects(await repo.list_prospects(session))
    return [{"dedupe_key": d.dedupe_key, "prospect_ids": d.prospect_ids} for d in dupes]


@router.get("/conflicts/cross-campaign")
async def get_cross_campaign_conflicts(session: AsyncSession = Depends(get_session)) -> list[dict]:
    conflicts = detect_cross_campaign_conflicts(await repo.list_all_links(session))
    return [
        {"prospect_id": c.prospect_id, "campaign_ids": c.campaign_ids, "reason": c.reason}
        for c in conflicts
    ]


# --- personas ----------------------------------------------------------------
@router.post("/{campaign_id}/personas", response_model=Persona)
async def create_persona(campaign_id: str, persona: Persona, session: AsyncSession = Depends(get_session)) -> Persona:
    await _require_campaign(session, campaign_id)
    persona.campaign_id = campaign_id
    return await repo.save_persona(session, persona)


@router.get("/{campaign_id}/personas", response_model=list[Persona])
async def list_personas(campaign_id: str, session: AsyncSession = Depends(get_session)) -> list[Persona]:
    await _require_campaign(session, campaign_id)
    return await repo.list_personas_for_campaign(session, campaign_id)


# --- campaign assets ---------------------------------------------------------
@router.post("/{campaign_id}/assets", response_model=CampaignAsset)
async def create_asset(campaign_id: str, asset: CampaignAsset, session: AsyncSession = Depends(get_session)) -> CampaignAsset:
    await _require_campaign(session, campaign_id)
    asset.campaign_id = campaign_id
    return await repo.save_asset(session, asset)


@router.get("/{campaign_id}/assets", response_model=list[CampaignAsset])
async def list_assets(campaign_id: str, session: AsyncSession = Depends(get_session)) -> list[CampaignAsset]:
    await _require_campaign(session, campaign_id)
    return await repo.list_assets_for_campaign(session, campaign_id)


# --- research agent invocation ------------------------------------------------
@router.post("/{campaign_id}/prospects/{link_id}/research")
async def run_research(campaign_id: str, link_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Runs Research on one prospect and applies its decision via the state
    machine. Agent only returns an AgentDecision; this endpoint transitions
    stage and persists (agents decide, orchestrator executes)."""
    campaign = await _require_campaign(session, campaign_id)
    link = await _require_link(session, link_id)
    prospect = await _require_prospect(session, link.prospect_id)
    personas = await repo.list_personas_for_campaign(session, campaign_id)

    context = AgentContext(campaign=campaign, prospect=prospect, link=link, personas=personas)
    decision = research_agent.run(context)  # wrap in run_in_threadpool if this ever blocks
    await repo.append_decision(session, decision)

    # Enrichment may have mutated prospect.profile in place — persist it.
    await repo.save_prospect(session, prospect)

    if link.stage == FunnelStage.DISCOVERED:
        sm.transition(link, FunnelStage.RESEARCHED, campaign)

    link.fit_score = decision.details.get("fit_score")
    link.qualification_reasoning = decision.reasoning
    if decision.details.get("persona_id"):
        link.persona_id = decision.details["persona_id"]

    if decision.verdict == DecisionVerdict.QUALIFY:
        sm.transition(link, FunnelStage.QUALIFIED, campaign)
    elif decision.verdict == DecisionVerdict.REJECT:
        sm.transition(link, FunnelStage.REJECTED, campaign)
    # NEEDS_REVIEW: stays at RESEARCHED.

    await repo.save_link(session, link)
    return {"link": link, "decision": decision}


@router.get("/{campaign_id}/prospects/{link_id}/decisions", response_model=list[AgentDecision])
async def get_decisions(campaign_id: str, link_id: str, session: AsyncSession = Depends(get_session)) -> list[AgentDecision]:
    link = await _require_link(session, link_id)
    return await repo.list_decisions_for_prospect(session, campaign_id, link.prospect_id)


# --- personalize agent invocation --------------------------------------------
@router.post("/{campaign_id}/prospects/{link_id}/personalize")
async def run_personalize(campaign_id: str, link_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Runs Personalize on a qualified prospect. Returns a draft + channel +
    timing decision. Does NOT send (connector) or schedule (APScheduler) — those
    aren't built yet; this stops at the decision, which is the agent's whole job.
    Refuses prospects on the suppression list."""
    campaign = await _require_campaign(session, campaign_id)
    link = await _require_link(session, link_id)
    prospect = await _require_prospect(session, link.prospect_id)
    if link.stage != FunnelStage.QUALIFIED:
        raise HTTPException(409, f"Prospect is at stage '{link.stage}', must be 'qualified' to personalize")

    # Do-not-contact guard.
    for key in (prospect.profile.linkedin_url, prospect.profile.work_email, prospect.profile.name):
        if key and await repo.is_suppressed(session, key):
            raise HTTPException(409, "Prospect is on the do-not-contact suppression list")

    personas = await repo.list_personas_for_campaign(session, campaign_id)
    assets = await repo.list_assets_for_campaign(session, campaign_id)

    agent = PersonalizeAgent(assets=assets)
    context = AgentContext(campaign=campaign, prospect=prospect, link=link, personas=personas)
    decision = agent.run(context)
    await repo.append_decision(session, decision)
    return {"decision": decision}


# --- converse agent invocation -----------------------------------------------
@router.post("/{campaign_id}/prospects/{link_id}/converse")
async def run_converse(campaign_id: str, link_id: str, body: ConverseRequest, session: AsyncSession = Depends(get_session)) -> dict:
    """Handle an inbound reply (from a channel connector later) or a manually
    triggered follow-up. Delegates to the shared service layer so the scheduler
    runs the identical logic when a follow-up timer fires."""
    campaign = await _require_campaign(session, campaign_id)
    link = await _require_link(session, link_id)
    prospect = await _require_prospect(session, link.prospect_id)

    return await service.process_converse(
        session, campaign, link, prospect,
        trigger=body.trigger, inbound_message=body.inbound_message, channel=body.channel,
    )


class ScheduleFollowUpRequest(BaseModel):
    delay_days: int = 3


@router.post("/{campaign_id}/prospects/{link_id}/schedule-follow-up")
async def schedule_follow_up(campaign_id: str, link_id: str, body: ScheduleFollowUpRequest, session: AsyncSession = Depends(get_session)) -> dict:
    """Schedule a follow-up timer for a contacted prospect. When it fires, the
    scheduler runs the same converse follow-up path via the service layer.
    Working-hours-aware; respects pause (parks + fires on resume)."""
    campaign = await _require_campaign(session, campaign_id)
    link = await _require_link(session, link_id)

    fire_at = sched.schedule_follow_up(campaign, link_id, delay_days=body.delay_days)
    link.next_follow_up_at = fire_at
    await repo.save_link(session, link)
    return {"scheduled_for": fire_at, "link_id": link_id}


# --- suppression / do-not-contact --------------------------------------------
@router.get("/suppression/list")
async def get_suppression_list(session: AsyncSession = Depends(get_session)) -> dict:
    return {"suppressed": await repo.list_suppression(session)}


@router.post("/suppression/add")
async def add_to_suppression(value: str, session: AsyncSession = Depends(get_session)) -> dict:
    await repo.add_suppression(session, value)
    return {"added": value}