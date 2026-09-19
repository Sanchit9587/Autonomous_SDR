"""FastAPI router for campaign + prospect control.

In-memory store for now (dicts). This is intentional: it lets the whole
orchestrator be built and demoed today, and gets swapped for real persistence
(core/db/, alembic) later without changing a single function signature here —
the store is the only thing that will change.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.base import AgentContext
from agents.converse.agent import ConverseAgent
from agents.personalize.agent import PersonalizeAgent
from agents.research.agent import ResearchAgent
from core.models import (
    AgentDecision,
    AgentSettings,
    Campaign,
    CampaignAsset,
    CampaignProspectLink,
    Channel,
    ConversationTurn,
    DecisionVerdict,
    Direction,
    FunnelStage,
    ICPFilter,
    Persona,
    Prospect,
)
from orchestrator import campaign_controller as cc
from orchestrator import state_machine as sm
from orchestrator.conflict_resolver import detect_cross_campaign_conflicts, find_duplicate_prospects
from orchestrator.suppression import SuppressionList

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# --- in-memory store -------------------------------------------------------
_campaigns: dict[str, Campaign] = {}
_prospects: dict[str, Prospect] = {}
_links: dict[str, CampaignProspectLink] = {}  # keyed by link.id
_personas: dict[str, Persona] = {}
_assets: dict[str, CampaignAsset] = {}
_decisions: list[AgentDecision] = []
_conversations: list[ConversationTurn] = []
suppression = SuppressionList()
kill_switch = cc.GlobalKillSwitch()
research_agent = ResearchAgent()  # zero-config default: no Apollo, template/Gemini/Groq reasoning per env
converse_agent = ConverseAgent()


# --- request/response payloads ---------------------------------------------
class CreateCampaignRequest(BaseModel):
    name: str
    owner: str
    description: Optional[str] = None
    icp: ICPFilter = ICPFilter()
    agent_settings: dict[str, AgentSettings] = {}
    default_channel_priority: list = []


class TransitionRequest(BaseModel):
    to_stage: FunnelStage
    reason: Optional[str] = None


def _get_campaign(campaign_id: str) -> Campaign:
    campaign = _campaigns.get(campaign_id)
    if campaign is None:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    return campaign


def _get_link(link_id: str) -> CampaignProspectLink:
    link = _links.get(link_id)
    if link is None:
        raise HTTPException(404, f"CampaignProspectLink {link_id} not found")
    return link


# --- campaign lifecycle ------------------------------------------------------
@router.post("", response_model=Campaign)
def create_campaign(body: CreateCampaignRequest) -> Campaign:
    campaign = Campaign(
        name=body.name, owner=body.owner, description=body.description, icp=body.icp,
        agent_settings=body.agent_settings, default_channel_priority=body.default_channel_priority,
    )
    _campaigns[campaign.id] = campaign
    return campaign


@router.get("", response_model=list[Campaign])
def list_campaigns() -> list[Campaign]:
    return list(_campaigns.values())


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str) -> Campaign:
    return _get_campaign(campaign_id)


def _lifecycle_endpoint(campaign_id: str, action):
    campaign = _get_campaign(campaign_id)
    try:
        action(campaign)
    except cc.InvalidCampaignStatusTransitionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return campaign


@router.post("/{campaign_id}/activate", response_model=Campaign)
def activate_campaign(campaign_id: str) -> Campaign:
    return _lifecycle_endpoint(campaign_id, cc.activate)


@router.post("/{campaign_id}/pause", response_model=Campaign)
def pause_campaign(campaign_id: str) -> Campaign:
    """Pausing one campaign never touches any other — verified in tests."""
    return _lifecycle_endpoint(campaign_id, cc.pause)


@router.post("/{campaign_id}/resume", response_model=Campaign)
def resume_campaign(campaign_id: str) -> Campaign:
    return _lifecycle_endpoint(campaign_id, cc.resume)


@router.post("/{campaign_id}/complete", response_model=Campaign)
def complete_campaign(campaign_id: str) -> Campaign:
    return _lifecycle_endpoint(campaign_id, cc.complete)


@router.post("/{campaign_id}/archive", response_model=Campaign)
def archive_campaign(campaign_id: str) -> Campaign:
    return _lifecycle_endpoint(campaign_id, cc.archive)


@router.post("/{campaign_id}/duplicate", response_model=Campaign)
def duplicate_campaign(campaign_id: str) -> Campaign:
    clone = cc.duplicate(_get_campaign(campaign_id))
    _campaigns[clone.id] = clone
    return clone


@router.post("/kill-switch/engage")
def engage_kill_switch() -> dict[str, bool]:
    kill_switch.engage()
    return {"engaged": True}


@router.post("/kill-switch/disengage")
def disengage_kill_switch() -> dict[str, bool]:
    kill_switch.disengage()
    return {"engaged": False}


# --- prospects + funnel transitions -----------------------------------------
@router.post("/{campaign_id}/prospects", response_model=CampaignProspectLink)
def add_prospect(campaign_id: str, prospect: Prospect) -> CampaignProspectLink:
    _get_campaign(campaign_id)  # 404 if missing
    _prospects[prospect.id] = prospect
    link = CampaignProspectLink(campaign_id=campaign_id, prospect_id=prospect.id)
    _links[link.id] = link
    return link


@router.get("/{campaign_id}/funnel")
def get_funnel(campaign_id: str) -> dict[str, int]:
    _get_campaign(campaign_id)
    campaign_links = [l for l in _links.values() if l.campaign_id == campaign_id]
    return sm.funnel_counts(campaign_links)


@router.post("/{campaign_id}/prospects/{link_id}/transition", response_model=CampaignProspectLink)
def transition_prospect(campaign_id: str, link_id: str, body: TransitionRequest) -> CampaignProspectLink:
    campaign = _get_campaign(campaign_id)
    link = _get_link(link_id)

    if kill_switch.is_engaged and body.to_stage in sm._OUTREACH_STAGES:
        raise HTTPException(423, "Global kill switch is engaged — no autonomous outreach permitted")

    try:
        sm.transition(link, body.to_stage, campaign, reason=body.reason)
    except sm.InvalidTransitionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except sm.CampaignNotLiveError as exc:
        raise HTTPException(409, str(exc)) from exc
    return link


@router.get("/conflicts/duplicates")
def get_duplicate_prospects() -> list[dict]:
    dupes = find_duplicate_prospects(list(_prospects.values()))
    return [{"dedupe_key": d.dedupe_key, "prospect_ids": d.prospect_ids} for d in dupes]


@router.get("/conflicts/cross-campaign")
def get_cross_campaign_conflicts() -> list[dict]:
    conflicts = detect_cross_campaign_conflicts(list(_links.values()))
    return [
        {"prospect_id": c.prospect_id, "campaign_ids": c.campaign_ids, "reason": c.reason}
        for c in conflicts
    ]


# --- personas ----------------------------------------------------------------
@router.post("/{campaign_id}/personas", response_model=Persona)
def create_persona(campaign_id: str, persona: Persona) -> Persona:
    _get_campaign(campaign_id)
    persona.campaign_id = campaign_id
    _personas[persona.id] = persona
    return persona


@router.get("/{campaign_id}/personas", response_model=list[Persona])
def list_personas(campaign_id: str) -> list[Persona]:
    _get_campaign(campaign_id)
    return [p for p in _personas.values() if p.campaign_id == campaign_id]


# --- research agent invocation ------------------------------------------------
@router.post("/{campaign_id}/prospects/{link_id}/research")
def run_research(campaign_id: str, link_id: str) -> dict:
    """Runs the Research agent on one prospect and applies its decision via
    the state machine. This is the orchestrator's job, not the agent's — the
    agent only returns an AgentDecision, this endpoint is what actually calls
    sm.transition() based on the verdict (agents decide, orchestrator executes)."""
    campaign = _get_campaign(campaign_id)
    link = _get_link(link_id)
    prospect = _prospects.get(link.prospect_id)
    if prospect is None:
        raise HTTPException(404, f"Prospect {link.prospect_id} not found")

    campaign_personas = [p for p in _personas.values() if p.campaign_id == campaign_id]
    context = AgentContext(campaign=campaign, prospect=prospect, link=link, personas=campaign_personas)
    decision = research_agent.run(context)
    _decisions.append(decision)

    # Advance Discovered -> Researched first, if not already past it.
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
    # NEEDS_REVIEW: stays at RESEARCHED, awaiting the human-approval gate.

    return {"link": link, "decision": decision}


@router.get("/{campaign_id}/prospects/{link_id}/decisions", response_model=list[AgentDecision])
def get_decisions(campaign_id: str, link_id: str) -> list[AgentDecision]:
    link = _get_link(link_id)
    return [d for d in _decisions if d.campaign_id == campaign_id and d.prospect_id == link.prospect_id]


# --- campaign assets ---------------------------------------------------------
@router.post("/{campaign_id}/assets", response_model=CampaignAsset)
def create_asset(campaign_id: str, asset: CampaignAsset) -> CampaignAsset:
    _get_campaign(campaign_id)
    asset.campaign_id = campaign_id
    _assets[asset.id] = asset
    return asset


@router.get("/{campaign_id}/assets", response_model=list[CampaignAsset])
def list_assets(campaign_id: str) -> list[CampaignAsset]:
    _get_campaign(campaign_id)
    return [a for a in _assets.values() if a.campaign_id == campaign_id]


# --- personalize agent invocation --------------------------------------------
@router.post("/{campaign_id}/prospects/{link_id}/personalize")
def run_personalize(campaign_id: str, link_id: str) -> dict:
    """Runs the Personalize agent on a qualified prospect. Returns a draft +
    channel + timing decision. Does NOT send — a SEND verdict is what the
    orchestrator would hand to a messaging connector, and a WAIT verdict's
    scheduled_time is what an APScheduler job would later fire on. Neither the
    connector nor the scheduler is built yet, so this endpoint stops at the
    decision (which is the agent's whole job)."""
    campaign = _get_campaign(campaign_id)
    link = _get_link(link_id)
    prospect = _prospects.get(link.prospect_id)
    if prospect is None:
        raise HTTPException(404, f"Prospect {link.prospect_id} not found")
    if link.stage != FunnelStage.QUALIFIED:
        raise HTTPException(409, f"Prospect is at stage '{link.stage}', must be 'qualified' to personalize")

    campaign_personas = [p for p in _personas.values() if p.campaign_id == campaign_id]
    campaign_assets = [a for a in _assets.values() if a.campaign_id == campaign_id]

    agent = PersonalizeAgent(assets=campaign_assets)
    context = AgentContext(campaign=campaign, prospect=prospect, link=link, personas=campaign_personas)
    decision = agent.run(context)
    _decisions.append(decision)

    return {"decision": decision}


# --- converse agent invocation -----------------------------------------------
class ConverseRequest(BaseModel):
    inbound_message: Optional[str] = None
    trigger: str = "reply"                 # "reply" | "follow_up"
    channel: Channel = Channel.EMAIL


@router.post("/{campaign_id}/prospects/{link_id}/converse")
def run_converse(campaign_id: str, link_id: str, body: ConverseRequest) -> dict:
    """Handle an inbound reply (from a channel connector, later) or a fired
    follow-up timer (from APScheduler, later). Today the inbound message is
    passed in the request body so it's testable without a live inbox.

    Applies the returned decision: records the inbound turn, transitions stage,
    suppresses on unsubscribe, and — when a reply is needed — re-invokes the
    Personalize agent (all drafting lives there)."""
    campaign = _get_campaign(campaign_id)
    link = _get_link(link_id)
    prospect = _prospects.get(link.prospect_id)
    if prospect is None:
        raise HTTPException(404, f"Prospect {link.prospect_id} not found")

    campaign_personas = [p for p in _personas.values() if p.campaign_id == campaign_id]
    history = [t for t in _conversations if t.campaign_id == campaign_id and t.prospect_id == link.prospect_id]

    # Record the inbound reply as a conversation turn.
    if body.trigger == "reply" and body.inbound_message:
        _conversations.append(ConversationTurn(
            campaign_id=campaign_id, prospect_id=link.prospect_id,
            channel=body.channel, direction=Direction.INBOUND, content=body.inbound_message,
        ))

    context = AgentContext(
        campaign=campaign, prospect=prospect, link=link, personas=campaign_personas,
        trigger=body.trigger, inbound_message=body.inbound_message, conversation_history=history,
    )
    decision = converse_agent.run(context)
    _decisions.append(decision)

    # --- orchestrator executes the decision ---
    follow_up_draft = None

    if decision.details.get("suppress"):
        suppression.add_prospect(prospect)

    target_stage = decision.details.get("target_stage")
    if target_stage:
        try:
            sm.transition(link, FunnelStage(target_stage), campaign)
        except (sm.InvalidTransitionError, sm.CampaignNotLiveError):
            pass  # keep current stage if the transition isn't valid from here

    # Loop-back: when a reply/follow-up message is needed, re-invoke Personalize.
    next_action = decision.details.get("next_action")
    if next_action in ("reply", "follow_up") and link.stage == FunnelStage.ENGAGED:
        campaign_assets = [a for a in _assets.values() if a.campaign_id == campaign_id]
        p_agent = PersonalizeAgent(assets=campaign_assets)
        p_decision = p_agent.run(context)
        _decisions.append(p_decision)
        follow_up_draft = p_decision

    return {"decision": decision, "personalize_followup": follow_up_draft}


# --- suppression / do-not-contact --------------------------------------------
@router.get("/suppression/list")
def get_suppression_list() -> dict:
    return {"suppressed": suppression.all()}


@router.post("/suppression/add")
def add_to_suppression(value: str) -> dict:
    suppression.add(value)
    return {"added": value}