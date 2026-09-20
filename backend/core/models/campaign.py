"""Campaign: the first-class object every agent and the orchestrator operate within.

See docs/campaign-lifecycle.md for the state machine this backs.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import CampaignStatus, Channel, ChannelMode, TimestampedModel, _new_id


class ICPFilter(BaseModel):
    """Targeting definition for a campaign's Ideal Customer Profile."""

    keywords: Optional[str] = None
    target_roles: list[str] = Field(default_factory=list)
    geography: list[str] = Field(default_factory=list)
    company_criteria: Optional[str] = None       # free text: size, industry, funding stage etc.
    company_size_min: Optional[int] = None        # e.g. 50  (Config "50-500")
    company_size_max: Optional[int] = None        # e.g. 500
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
    """Per-channel operating limits + execution mode for a campaign."""

    channel: Channel
    enabled: bool = True
    mode: ChannelMode = ChannelMode.APPROVAL     # automate / approval / manual
    daily_limit: Optional[int] = None
    working_hours: Optional[str] = None            # e.g. "09:00-18:00 IST"
    cpm: Optional[float] = None                    # cost-per-mille, for budget/metrics


class Campaign(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("camp"))
    name: str
    description: Optional[str] = None
    vision_statement: Optional[str] = None         # Config "Campaign Vision Statement"
    owner: str                                      # rep/user id
    status: CampaignStatus = CampaignStatus.DRAFT

    icp: ICPFilter = Field(default_factory=ICPFilter)
    agent_settings: dict[str, AgentSettings] = Field(default_factory=dict)   # keyed by AgentName
    channel_policies: list[ChannelPolicy] = Field(default_factory=list)
    # Fallback channel order when a prospect's persona doesn't specify its own
    # (see Persona.effective_channel_priority).
    default_channel_priority: list[Channel] = Field(default_factory=list)

    # Strategy / execution config (Campaign Config + Summary screens):
    budget: Optional[float] = None
    start_date: Optional[str] = None               # ISO date
    end_date: Optional[str] = None
    target_scale: Optional[int] = None             # target prospects/impressions
    pace_per_day: Optional[int] = None             # touches/day
    goals: list[str] = Field(default_factory=list) # e.g. ["book_meeting", "signup"]
    sources: list[str] = Field(default_factory=lambda: ["apollo", "linkedin"]) # Apollo, LinkedIn, CSV
    connector_configs: dict[str, dict] = Field(default_factory=dict)            # per-connector config/status

    system_prompt_version: Optional[str] = None      # campaign-level PromptVersion.id
    assigned_rep_ids: list[str] = Field(default_factory=list)

    # The visual Choreography Builder's saved graph: {"nodes": [...], "edges": [...]}
    # in React Flow's native shape. Not yet interpreted by anything — the campaign
    # still runs on the hardcoded state machine + follow-up policy (see
    # orchestrator/state_machine.py). This is Phase 1 (build + persist the graph);
    # an executor that actually runs campaigns off this graph is a separate,
    # larger piece of work. Left as a loose dict rather than a typed model since
    # the schema is still React Flow's, not ours, until the executor exists.
    choreography: Optional[dict] = None

    def is_live(self) -> bool:
        return self.status == CampaignStatus.LIVE