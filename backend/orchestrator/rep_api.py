"""Rep-facing read API (the teal 'operational' app: Mark Anders).

Read-only views over data the agents already produce. Any authenticated user
(rep, manager, or admin) can read these — they're monitoring views, not the
control plane. Rep-scoping (only campaigns a rep is assigned to) is applied for
users whose role is exactly 'rep'; managers/admins see everything.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from core.db import repository as repo
from core.db.engine import get_session
from core.models import AgentDecision, Campaign, CampaignProspectLink, Prospect, User
from core.models.base import UserRole
from orchestrator import state_machine as sm

router = APIRouter(prefix="/rep", tags=["rep"], dependencies=[Depends(get_current_user)])


def _visible_to(user: User, campaign: Campaign) -> bool:
    """Managers/admins see all; a rep sees campaigns they own or are assigned to."""
    if user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return True
    return user.id == campaign.owner or user.id in campaign.assigned_rep_ids


# --- combined shapes returned to the rep UI ---------------------------------
class ProspectRow(BaseModel):
    link: CampaignProspectLink
    prospect: Prospect


class CampaignOverview(BaseModel):
    campaign: Campaign
    funnel: dict[str, int]
    open_escalations: int


@router.get("/campaigns", response_model=list[Campaign])
async def rep_campaigns(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[Campaign]:
    """Campaigns this user can see (rep-scoped for reps)."""
    campaigns = await repo.list_campaigns(session)
    return [c for c in campaigns if _visible_to(user, c)]


@router.get("/campaigns/{campaign_id}/overview", response_model=CampaignOverview)
async def rep_campaign_overview(campaign_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> CampaignOverview:
    campaign = await repo.get_campaign(session, campaign_id)
    if campaign is None or not _visible_to(user, campaign):
        raise HTTPException(404, "Campaign not found")
    links = await repo.list_links_for_campaign(session, campaign_id)
    escalations = await repo.list_escalations(session, campaign_id)
    return CampaignOverview(campaign=campaign, funnel=sm.funnel_counts(links), open_escalations=len(escalations))


@router.get("/campaigns/{campaign_id}/prospects", response_model=list[ProspectRow])
async def rep_prospects(campaign_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[ProspectRow]:
    """The Prospects list — every prospect in the campaign with its funnel state.
    (This is the 'list prospects for a campaign' endpoint the Prospects page needed.)"""
    campaign = await repo.get_campaign(session, campaign_id)
    if campaign is None or not _visible_to(user, campaign):
        raise HTTPException(404, "Campaign not found")
    pairs = await repo.list_prospects_for_campaign(session, campaign_id)
    return [ProspectRow(link=link, prospect=prospect) for link, prospect in pairs]


@router.get("/activity", response_model=list[AgentDecision])
async def rep_activity(
    campaign_id: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AgentDecision]:
    """Live Activity feed — newest agent decisions first. If campaign_id is given
    and the rep can't see it, returns empty rather than erroring."""
    if campaign_id:
        campaign = await repo.get_campaign(session, campaign_id)
        if campaign is None or not _visible_to(user, campaign):
            return []
    decisions = await repo.list_recent_decisions(session, campaign_id, limit=min(limit, 200))
    # For reps, filter to visible campaigns when not scoped to one.
    if not campaign_id and user.role == UserRole.REP:
        visible = {c.id for c in await repo.list_campaigns(session) if _visible_to(user, c)}
        decisions = [d for d in decisions if d.campaign_id in visible]
    return decisions


@router.get("/escalations", response_model=list[AgentDecision])
async def rep_escalations(
    campaign_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AgentDecision]:
    """Escalations queue — agent decisions that routed to a human."""
    if campaign_id:
        campaign = await repo.get_campaign(session, campaign_id)
        if campaign is None or not _visible_to(user, campaign):
            return []
    escalations = await repo.list_escalations(session, campaign_id)
    if not campaign_id and user.role == UserRole.REP:
        visible = {c.id for c in await repo.list_campaigns(session) if _visible_to(user, c)}
        escalations = [e for e in escalations if e.campaign_id in visible]
    return escalations