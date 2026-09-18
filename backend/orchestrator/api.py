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

from core.models import Campaign, CampaignProspectLink, FunnelStage, ICPFilter, Prospect
from orchestrator import campaign_controller as cc
from orchestrator import state_machine as sm
from orchestrator.conflict_resolver import detect_cross_campaign_conflicts, find_duplicate_prospects

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# --- in-memory store -------------------------------------------------------
_campaigns: dict[str, Campaign] = {}
_prospects: dict[str, Prospect] = {}
_links: dict[str, CampaignProspectLink] = {}  # keyed by link.id
kill_switch = cc.GlobalKillSwitch()


# --- request/response payloads ---------------------------------------------
class CreateCampaignRequest(BaseModel):
    name: str
    owner: str
    description: Optional[str] = None
    icp: ICPFilter = ICPFilter()


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
    campaign = Campaign(name=body.name, owner=body.owner, description=body.description, icp=body.icp)
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