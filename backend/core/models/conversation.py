"""ConversationTurn: one message in an ongoing outreach thread, any channel."""
from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import Channel, TimestampedModel, _new_id


class Direction(StrEnum):
    OUTBOUND = "outbound"    # agent/rep -> prospect
    INBOUND = "inbound"      # prospect -> agent/rep


class ConversationTurn(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("turn"))
    campaign_id: str
    prospect_id: str
    channel: Channel
    direction: Direction

    content: str
    agent_name: Optional[str] = None          # which agent generated this (outbound only)
    prompt_version_id: Optional[str] = None

    # For voice specifically
    call_duration_seconds: Optional[int] = None
    transcript_confidence: Optional[float] = None