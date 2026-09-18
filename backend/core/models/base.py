"""Shared base classes and enums used across every model in core/."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TimestampedModel(BaseModel):
    """Every persisted object gets these for free."""

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Channel(StrEnum):
    LINKEDIN = "linkedin"
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"


class FunnelStage(StrEnum):
    """The pipeline stage a prospect sits in, inside one campaign."""

    DISCOVERED = "discovered"
    RESEARCHED = "researched"
    QUALIFIED = "qualified"
    REJECTED = "rejected"          # terminal — Research agent said no
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    MEETING = "meeting"
    OPPORTUNITY = "opportunity"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    LIVE = "live"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AgentName(StrEnum):
    RESEARCH = "research"
    PERSONALIZE = "personalize"
    CONVERSE = "converse"


class DecisionVerdict(StrEnum):
    QUALIFY = "qualify"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"
    APPROVE = "approve"            # human-approval gate outcomes
    HOLD = "hold"
    SEND = "send"                  # personalize/outreach decisions
    WAIT = "wait"
    ESCALATE = "escalate"          # converse decisions
    CONTINUE = "continue"


__all__ = [
    "TimestampedModel",
    "Channel",
    "FunnelStage",
    "CampaignStatus",
    "AgentName",
    "DecisionVerdict",
    "_new_id",
]