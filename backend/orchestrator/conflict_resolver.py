"""Conflict detection (PS section 3: Campaign Isolation & Conflict Handling).

Handles: the same prospect appearing in multiple campaigns, two campaigns
targeting the same prospect at once, and excessive contact frequency.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from core.models import CampaignProspectLink, FunnelStage, Prospect

_ACTIVE_STAGES = {
    FunnelStage.QUALIFIED,
    FunnelStage.CONTACTED,
    FunnelStage.ENGAGED,
    FunnelStage.MEETING,
}


@dataclass
class DuplicateProspectGroup:
    dedupe_key: str
    prospect_ids: list[str] = field(default_factory=list)


def find_duplicate_prospects(prospects: list[Prospect]) -> list[DuplicateProspectGroup]:
    """Group prospects that are actually the same person (same LinkedIn URL / email /
    name) but exist as separate Prospect rows, e.g. discovered independently by two
    campaigns' scrapers."""
    groups: dict[str, list[str]] = defaultdict(list)
    for p in prospects:
        groups[p.dedupe_key()].append(p.id)
    return [
        DuplicateProspectGroup(dedupe_key=key, prospect_ids=ids)
        for key, ids in groups.items()
        if len(ids) > 1
    ]


@dataclass
class CrossCampaignConflict:
    prospect_id: str
    campaign_ids: list[str]
    reason: str


def detect_cross_campaign_conflicts(links: list[CampaignProspectLink]) -> list[CrossCampaignConflict]:
    """Find prospects that are simultaneously in an active (post-qualification)
    stage in more than one campaign — this is the "two campaigns targeting the
    same prospect at once" case the PS calls out."""
    by_prospect: dict[str, list[CampaignProspectLink]] = defaultdict(list)
    for link in links:
        if link.stage in _ACTIVE_STAGES:
            by_prospect[link.prospect_id].append(link)

    conflicts: list[CrossCampaignConflict] = []
    for prospect_id, prospect_links in by_prospect.items():
        campaign_ids = {l.campaign_id for l in prospect_links}
        if len(campaign_ids) > 1:
            conflicts.append(
                CrossCampaignConflict(
                    prospect_id=prospect_id,
                    campaign_ids=sorted(campaign_ids),
                    reason="Prospect is active in multiple campaigns simultaneously",
                )
            )
    return conflicts


def is_contact_frequency_exceeded(
    link: CampaignProspectLink,
    *,
    max_contacts_per_week: int = 3,
) -> bool:
    """Simple guard against over-contacting one person within one campaign.
    A full implementation would look at actual ConversationTurn timestamps;
    this uses the link's running contact_count as a cheap proxy for the demo."""
    return link.contact_count >= max_contacts_per_week


def resolve_conflict(conflict: CrossCampaignConflict, links: list[CampaignProspectLink]) -> str:
    """Default resolution policy: keep the campaign where the prospect is furthest
    along the funnel active, suppress outreach in the others. Returns the
    campaign_id that stays active. Callers apply this by pausing/suppressing the
    losing links themselves (kept explicit rather than mutating here)."""
    stage_rank = {stage: i for i, stage in enumerate(FunnelStage)}
    relevant = [l for l in links if l.prospect_id == conflict.prospect_id and l.campaign_id in conflict.campaign_ids]
    winner = max(relevant, key=lambda l: stage_rank[l.stage])
    return winner.campaign_id