"""Prospect: a person, and their state within one specific campaign.

A prospect may appear in multiple campaigns (PS requirement), so funnel stage and
qualification are stored per (prospect, campaign) pair, not on the prospect itself.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import FunnelStage, TimestampedModel, _new_id


class ProspectProfile(BaseModel):
    """Static-ish facts about a person, shared across every campaign they're in."""

    name: str
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    position: Optional[str] = None
    company_name: Optional[str] = None
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