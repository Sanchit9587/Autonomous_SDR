"""The Discovered -> ... -> Opportunity state machine (PS section 3, campaign dashboard funnel).

Pure functions operating on core.models objects — no DB, no I/O. This is what lets
it be built and fully unit-tested before any persistence layer exists.
"""
from __future__ import annotations

from typing import Optional

from core.models import Campaign, CampaignProspectLink, CampaignStatus, FunnelStage

# Which stages a prospect may move to from its current stage.
# REJECTED is reachable from every non-terminal stage (a "stop" is always safe).
_ALLOWED_TRANSITIONS: dict[FunnelStage, set[FunnelStage]] = {
    FunnelStage.DISCOVERED: {FunnelStage.RESEARCHED, FunnelStage.REJECTED},
    FunnelStage.RESEARCHED: {FunnelStage.QUALIFIED, FunnelStage.REJECTED},
    FunnelStage.QUALIFIED: {FunnelStage.CONTACTED, FunnelStage.REJECTED},
    FunnelStage.CONTACTED: {FunnelStage.ENGAGED, FunnelStage.REJECTED},
    FunnelStage.ENGAGED: {FunnelStage.MEETING, FunnelStage.CONTACTED, FunnelStage.REJECTED},
    FunnelStage.MEETING: {FunnelStage.OPPORTUNITY, FunnelStage.REJECTED},
    FunnelStage.OPPORTUNITY: set(),   # terminal
    FunnelStage.REJECTED: set(),      # terminal
}

# Stages that represent the system taking autonomous, outward-facing action.
# These are the ones a Paused or Draft campaign must never reach.
_OUTREACH_STAGES = {FunnelStage.CONTACTED, FunnelStage.ENGAGED, FunnelStage.MEETING, FunnelStage.OPPORTUNITY}


class InvalidTransitionError(Exception):
    """Raised when a stage jump isn't in the allowed graph."""


class CampaignNotLiveError(Exception):
    """Raised when a transition requiring autonomous action is attempted on a
    campaign that is Draft, Paused, Completed or Archived."""


def can_transition(from_stage: FunnelStage, to_stage: FunnelStage) -> bool:
    return to_stage in _ALLOWED_TRANSITIONS.get(from_stage, set())


def transition(
    link: CampaignProspectLink,
    to_stage: FunnelStage,
    campaign: Campaign,
    *,
    reason: Optional[str] = None,
) -> CampaignProspectLink:
    """Move a prospect to a new funnel stage, enforcing the transition graph and
    the campaign's current status. Returns the same link object, mutated.

    REJECTED is always allowed regardless of campaign status — stopping outreach
    is never blocked, only starting/continuing it is.
    """
    if link.campaign_id != campaign.id:
        raise ValueError(f"link.campaign_id ({link.campaign_id}) does not match campaign.id ({campaign.id})")

    if not can_transition(link.stage, to_stage):
        raise InvalidTransitionError(
            f"Cannot move from {link.stage} to {to_stage}; "
            f"allowed next stages: {sorted(_ALLOWED_TRANSITIONS.get(link.stage, set()))}"
        )

    if to_stage in _OUTREACH_STAGES and campaign.status != CampaignStatus.LIVE:
        raise CampaignNotLiveError(
            f"Campaign {campaign.id} is {campaign.status}, not live — "
            f"cannot move prospect into outreach stage {to_stage}"
        )

    link.stage = to_stage
    if reason:
        link.qualification_reasoning = reason
    return link


def funnel_counts(links: list[CampaignProspectLink]) -> dict[str, int]:
    """Quick aggregation for the campaign dashboard: how many prospects per stage."""
    counts = {stage.value: 0 for stage in FunnelStage}
    for link in links:
        counts[link.stage.value] += 1
    return counts