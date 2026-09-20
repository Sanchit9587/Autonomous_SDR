"""The common contract every agent follows: agents decide, the orchestrator
executes. No agent calls state_machine.transition(), sends anything, or
mutates a Campaign/CampaignProspectLink directly — it returns an AgentDecision
(and, when relevant, an updated Prospect) and hands it back.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, ConfigDict

from core.models import AgentDecision, Campaign, CampaignProspectLink, ConversationTurn, Persona, Prospect


class AgentContext(BaseModel):
    """Everything an agent might need for one invocation. Agents read only
    what they need from this — e.g. Research ignores conversation history."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    campaign: Campaign
    prospect: Prospect
    link: CampaignProspectLink
    personas: list[Persona] = []
    prompt_version_id: Optional[str] = None

    # Converse-specific (optional; unused by Research/Personalize):
    trigger: Optional[str] = None                 # "reply" | "follow_up"
    inbound_message: Optional[str] = None         # the raw reply text, when trigger == "reply"
    conversation_history: list[ConversationTurn] = []

    # Pace/limit awareness (optional; used by Personalize channel selection):
    usage_today: dict[str, int] = {}              # outbound touches per channel today
    total_today: int = 0                          # total outbound touches today (campaign-wide)


class Agent(ABC):
    @abstractmethod
    def run(self, context: AgentContext) -> AgentDecision:
        """Return a decision. Must never raise on malformed/missing data —
        degrade to DecisionVerdict.NEEDS_REVIEW with a reasoning string
        explaining what was missing, rather than crashing the pipeline."""
        raise NotImplementedError