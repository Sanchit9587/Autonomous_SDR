"""Campaign: the first-class object every agent and the orchestrator operate within.

See docs/campaign-lifecycle.md for the state machine this backs.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import CampaignStatus, Channel, TimestampedModel, _new_id


class ICPFilter(BaseModel):
    """Targeting definition for a campaign's Ideal Customer Profile."""

    keywords: Optional[str] = None
    target_roles: list[str] = Field(default_factory=list)
    geography: list[str] = Field(default_factory=list)
    company_criteria: Optional[str] = None       # free text: size, industry, funding stage etc.
    exclusion_criteria: Optional[str] = None
    sample_profile_urls: list[str] = Field(default_factory=list)   # reference "good fit" profiles


class AgentSettings(BaseModel):
    """Per-agent configuration inside one campaign. One of these per AgentName."""

    enabled: bool = True
    active_prompt_version: Optional[str] = None   # PromptVersion.id currently live for this agent
    decision_threshold: Optional[float] = None    # e.g. min fit_score to auto-qualify
    tools_allowed: list[str] = Field(default_factory=list)
    escalation_rules: Optional[str] = None


class ChannelPolicy(BaseModel):
    """Per-channel operating limits for a campaign."""

    channel: Channel
    enabled: bool = True
    daily_limit: Optional[int] = None
    working_hours: Optional[str] = None            # e.g. "09:00-18:00 IST"


class Campaign(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("camp"))
    name: str
    description: Optional[str] = None
    owner: str                                      # rep/user id
    status: CampaignStatus = CampaignStatus.DRAFT

    icp: ICPFilter = Field(default_factory=ICPFilter)
    agent_settings: dict[str, AgentSettings] = Field(default_factory=dict)   # keyed by AgentName
    channel_policies: list[ChannelPolicy] = Field(default_factory=list)
    # Fallback channel order when a prospect's persona doesn't specify its own
    # (see Persona.effective_channel_priority).
    default_channel_priority: list[Channel] = Field(default_factory=list)

    system_prompt_version: Optional[str] = None      # campaign-level PromptVersion.id
    assigned_rep_ids: list[str] = Field(default_factory=list)

    def is_live(self) -> bool:
        return self.status == CampaignStatus.LIVE