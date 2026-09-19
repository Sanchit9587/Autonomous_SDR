"""Persona: a target-buyer segment within one campaign.

Replaces the earlier idea of a per-prospect channel-order override. A prospect
is assigned to a persona (by the Research agent, at qualification time), and
the persona — not the individual prospect — is what the outreach person
configures: channel order, tone, message templates, importance, follow-up
aggressiveness.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import Channel, ToneEnum, TimestampedModel, _new_id


class MessageTemplate(BaseModel):
    """A user-supplied template for one channel, for one persona.

    Personalize fills placeholders like {{first_name}}, {{company}} and adapts
    lightly around them, rather than free-generating from scratch — reduces
    hallucination risk and keeps the outreach person in control of the copy.
    """

    channel: Channel
    subject_template: Optional[str] = None      # email only
    body_template: str
    default_asset_ids: list[str] = Field(default_factory=list)   # CampaignAsset.id refs


class FollowUpPolicy(BaseModel):
    max_attempts: int = 3
    min_days_between: int = 3


class Persona(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("persona"))
    campaign_id: str
    name: str                                    # e.g. "Technical Founder"
    description: Optional[str] = None

    # Research agent uses this as extra retrieval context when classifying
    # which persona a prospect matches, on top of the campaign's base ICP.
    qualification_notes: Optional[str] = None

    importance: float = 1.0                      # 1.0 = normal; higher = higher triage priority
    tone: ToneEnum = ToneEnum.PROFESSIONAL
    tone_notes: Optional[str] = None              # escape hatch beyond the fixed enum

    channel_priority: list[Channel] = Field(default_factory=list)   # overrides campaign default
    templates: dict[str, MessageTemplate] = Field(default_factory=dict)  # keyed by Channel value
    # Few-shot examples of messages that worked for this persona, keyed by Channel
    # value, e.g. {"email": ["Hi {{first_name}}...", ...]}. Retrieved by the
    # Personalize agent to ground free-generation when no template applies.
    example_messages: dict[str, list[str]] = Field(default_factory=dict)
    follow_up_policy: FollowUpPolicy = Field(default_factory=FollowUpPolicy)

    def effective_channel_priority(self, campaign_default: list[Channel]) -> list[Channel]:
        return self.channel_priority or campaign_default

    def template_for(self, channel: Channel) -> Optional[MessageTemplate]:
        return self.templates.get(channel.value)