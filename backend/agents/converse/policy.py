"""Deterministic decision policy for Converse. Not an LLM call: once the reply
is classified, the next action is a lookup + a few guards. Explicit and
auditable — a judge can see exactly why the agent escalated or stopped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from agents.converse.classifier import Classification
from core.models import DecisionVerdict, FollowUpPolicy, FunnelStage

# Below this classifier confidence, escalate to a human rather than act on a guess.
LOW_CONFIDENCE_ESCALATION_THRESHOLD = 0.4


@dataclass
class PolicyOutcome:
    verdict: DecisionVerdict          # CONTINUE | ESCALATE | WAIT | REJECT
    next_action: str                  # "reply" | "advance_meeting" | "follow_up" | "stop" | "human" | "none"
    target_stage: Optional[FunnelStage]
    reason: str
    suppress: bool = False            # add prospect to do-not-contact (unsubscribe)


# category -> (verdict, next_action, target_stage)
_CATEGORY_POLICY: dict[str, PolicyOutcome] = {
    "positive":        PolicyOutcome(DecisionVerdict.CONTINUE, "reply", FunnelStage.ENGAGED, "positive reply — continue the conversation"),
    "meeting_request": PolicyOutcome(DecisionVerdict.CONTINUE, "advance_meeting", FunnelStage.MEETING, "prospect wants to meet"),
    "question":        PolicyOutcome(DecisionVerdict.CONTINUE, "reply", FunnelStage.ENGAGED, "prospect asked a question — answer it"),
    "objection":       PolicyOutcome(DecisionVerdict.CONTINUE, "reply", FunnelStage.ENGAGED, "objection raised — address it"),
    "out_of_office":   PolicyOutcome(DecisionVerdict.WAIT, "follow_up", None, "auto-reply / OOO — retry later"),
    "negative":        PolicyOutcome(DecisionVerdict.WAIT, "follow_up", None, "soft no — let follow-up policy decide"),
    "unsubscribe":     PolicyOutcome(DecisionVerdict.REJECT, "stop", FunnelStage.REJECTED, "explicit opt-out", suppress=True),
}

# Categories that always go to a human regardless of confidence.
_ALWAYS_ESCALATE_KEYWORDS = ["legal", "lawyer", "contract terms", "refund", "complaint", "angry"]


def decide_on_reply(classification: Classification, inbound_message: str) -> PolicyOutcome:
    # Hard escalation on sensitive content, checked on the raw message text.
    lowered = inbound_message.lower()
    if any(kw in lowered for kw in _ALWAYS_ESCALATE_KEYWORDS):
        return PolicyOutcome(DecisionVerdict.ESCALATE, "human", None, "sensitive content — routed to a human")

    # Low-confidence classification -> escalate rather than guess.
    if classification.confidence < LOW_CONFIDENCE_ESCALATION_THRESHOLD:
        return PolicyOutcome(DecisionVerdict.ESCALATE, "human", None,
                             f"low classification confidence ({classification.confidence:.2f}) — routed to a human")

    return _CATEGORY_POLICY.get(
        classification.category,
        PolicyOutcome(DecisionVerdict.ESCALATE, "human", None, "unrecognized category — routed to a human"),
    )


def decide_on_follow_up(
    contact_count: int,
    last_contact_at: Optional[datetime],
    policy: FollowUpPolicy,
    *,
    importance: float = 1.0,
    now: Optional[datetime] = None,
) -> PolicyOutcome:
    """Timer-fired case: decide whether to nudge again or give up."""
    now = now or datetime.now(timezone.utc)

    if contact_count >= policy.max_attempts:
        # High-importance personas escalate to a human instead of silently dying.
        if importance >= 2.0:
            return PolicyOutcome(DecisionVerdict.ESCALATE, "human", None,
                                 "max follow-ups reached on a high-importance prospect — handing to a human")
        return PolicyOutcome(DecisionVerdict.REJECT, "stop", FunnelStage.REJECTED,
                             f"max follow-ups ({policy.max_attempts}) reached — stopping")

    if last_contact_at is not None:
        # A datetime loaded from the DB may be timezone-naive; assume UTC so the
        # subtraction below never mixes naive and aware datetimes.
        if last_contact_at.tzinfo is None:
            last_contact_at = last_contact_at.replace(tzinfo=timezone.utc)
        days_since = (now - last_contact_at).days
        if days_since < policy.min_days_between:
            return PolicyOutcome(DecisionVerdict.WAIT, "none", None,
                                 f"only {days_since}d since last contact (min {policy.min_days_between}d) — wait")

    return PolicyOutcome(DecisionVerdict.CONTINUE, "follow_up", None,
                         f"follow-up #{contact_count + 1} of {policy.max_attempts}")