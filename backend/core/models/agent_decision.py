"""AgentDecision + PromptVersion: the audit trail behind every "why did it do that?".

Every meaningful agent action writes one AgentDecision, tagged with the exact
prompt version that produced it. This is what the PS's prompt-versioning and
"why did the agent behave this way" requirements need under the hood.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from core.models.base import AgentName, DecisionVerdict, TimestampedModel, _new_id


class PromptVersion(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("prompt"))
    campaign_id: str
    agent_name: AgentName
    version_number: int
    content: str                        # the actual prompt/system-message text
    is_active: bool = False
    created_by: Optional[str] = None
    change_note: Optional[str] = None


class AgentDecision(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("decision"))
    campaign_id: str
    prospect_id: str
    agent_name: AgentName
    prompt_version_id: Optional[str] = None    # which PromptVersion produced this

    verdict: DecisionVerdict
    reasoning: str
    confidence: Optional[float] = None          # 0-1, model's own confidence if available

    # Structured output specific to the agent — e.g. Research's matched/failed
    # ICP criteria, or Personalize's chosen channel + draft message id.
    details: dict[str, Any] = Field(default_factory=dict)

    tokens_used: Optional[int] = None
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None