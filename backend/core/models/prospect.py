"""Prospect: a person, and their state within one specific campaign.

A prospect may appear in multiple campaigns (PS requirement), so funnel stage and
qualification are stored per (prospect, campaign) pair, not on the prospect itself.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import FunnelStage, TimestampedModel, _new_id


class ProspectProfile(BaseModel):
    """Static-ish facts about a prospect, shared across every campaign they're in.

    Usually a person, but a prospect can also be company-centric (e.g. leads
    surfaced by the discovery pipeline before a named contact is identified):
    in that case `name`/`company_name` are the business name and `position`
    is left unset.
    """

    name: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    position: Optional[str] = None
    company_name: Optional[str] = None
    company_size: Optional[int] = None       # employee count, when enrichment provides it
    work_email: Optional[str] = None
    phone_numbers: list[str] = Field(default_factory=list)
    enrichment_status: str = "pending"   # pending | ok | partial | not_found | error


class Prospect(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("prospect"))
    profile: ProspectProfile

    def dedupe_key(self) -> str:
        """Used by the orchestrator's conflict resolver to detect the same person
        surfacing again, e.g. via linkedin_url or email."""
        return (self.profile.linkedin_url or self.profile.work_email or self.profile.name).lower()


class CampaignProspectLink(TimestampedModel):
    """The per-campaign state of a prospect — this is what actually moves through the funnel."""

    id: str = Field(default_factory=lambda: _new_id("link"))
    campaign_id: str
    prospect_id: str

    stage: FunnelStage = FunnelStage.DISCOVERED
    fit_score: Optional[float] = None            # 0-100, set by Research agent
    qualification_reasoning: Optional[str] = None
    persona_id: Optional[str] = None             # Persona.id, assigned by Research at qualification

    human_approved: bool = False
    human_approved_by: Optional[str] = None

    last_contacted_channel: Optional[str] = None
    contact_count: int = 0

    # Follow-up scheduling state (used by the scheduler):
    # - follow_up_owed: a follow-up timer fired while the campaign was paused, so
    #   it's owed and must fire on resume (now or next working window).
    # - next_follow_up_at: ISO UTC timestamp of the currently scheduled follow-up,
    #   if any (informational / for the dashboard).
    follow_up_owed: bool = False
    next_follow_up_at: Optional[str] = None

    # Manual input for the LTV/CAC dashboard metric — a manager fills this in
    # once a deal closes (won at 'opportunity' stage or later). Not agent-set:
    # there's no automatic revenue signal anywhere in the system yet.
    deal_value: Optional[float] = None