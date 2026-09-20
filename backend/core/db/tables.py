"""SQLAlchemy ORM tables — the storage layer, mirroring core/models/ (the
API/validation layer). Kept deliberately separate: Pydantic validates what
crosses the wire, these persist what sits on disk. mappers.py converts between.

Nested/variable-shape fields (ICP, agent_settings, templates, decision details)
are stored as JSON columns — pragmatic for a hackathon and keeps the schema
mirroring the Pydantic models 1:1 without a table per nested object.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class CampaignORM(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    icp: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    channel_policies: Mapped[list] = mapped_column(JSON, default=list)
    default_channel_priority: Mapped[list] = mapped_column(JSON, default=list)

    budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_scale: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pace_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    goals: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    connector_configs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    system_prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assigned_rep_ids: Mapped[list] = mapped_column(JSON, default=list)
    choreography: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class ProspectORM(TimestampMixin, Base):
    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # full ProspectProfile


class CampaignProspectLinkORM(TimestampMixin, Base):
    __tablename__ = "campaign_prospect_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    prospect_id: Mapped[str] = mapped_column(String, ForeignKey("prospects.id"), index=True)
    stage: Mapped[str] = mapped_column(String, default="discovered")
    fit_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qualification_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    human_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    human_approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_contacted_channel: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    contact_count: Mapped[int] = mapped_column(Integer, default=0)
    follow_up_owed: Mapped[bool] = mapped_column(Boolean, default=False)
    next_follow_up_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deal_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class PersonaORM(TimestampMixin, Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qualification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=1.0)
    tone: Mapped[str] = mapped_column(String, default="professional")
    tone_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel_priority: Mapped[list] = mapped_column(JSON, default=list)
    templates: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    example_messages: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    follow_up_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CampaignAssetORM(TimestampMixin, Base):
    __tablename__ = "campaign_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)


class PromptVersionORM(TimestampMixin, Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AgentDecisionORM(TimestampMixin, Base):
    __tablename__ = "agent_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    prospect_id: Mapped[str] = mapped_column(String, ForeignKey("prospects.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ConversationTurnORM(TimestampMixin, Base):
    __tablename__ = "conversation_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("campaigns.id"), index=True)
    prospect_id: Mapped[str] = mapped_column(String, ForeignKey("prospects.id"), index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    call_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transcript_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class SuppressionEntryORM(Base):
    __tablename__ = "suppression_entries"

    key: Mapped[str] = mapped_column(String, primary_key=True)  # normalised identifier
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class UserORM(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="rep")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)