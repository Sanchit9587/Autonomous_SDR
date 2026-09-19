"""The Converse agent.

Two triggers:
  * trigger="reply"     -> classify the inbound message, apply reply policy.
  * trigger="follow_up" -> apply follow-up policy (no message to classify).

Returns an AgentDecision only. It never drafts message text itself — when a
reply/follow-up is needed, next_action tells the orchestrator to re-invoke the
Personalize agent (all customer-facing copy lives in one agent). It also never
transitions stage, sends, or suppresses directly — the orchestrator does those
based on the returned verdict/next_action.
"""
from __future__ import annotations

from typing import Optional

from agents.base import Agent, AgentContext
from agents.converse.classifier import ReplyClassifier, default_classifier
from agents.converse.policy import decide_on_follow_up, decide_on_reply
from core.models import AgentDecision, AgentName, DecisionVerdict, FollowUpPolicy, Persona


class ConverseAgent(Agent):
    def __init__(self, *, classifier: Optional[ReplyClassifier] = None) -> None:
        self.classifier = classifier or default_classifier()

    def run(self, context: AgentContext) -> AgentDecision:
        if context.trigger == "follow_up":
            return self._handle_follow_up(context)
        return self._handle_reply(context)

    def _handle_reply(self, context: AgentContext) -> AgentDecision:
        message = context.inbound_message or ""
        if not message.strip():
            return AgentDecision(
                campaign_id=context.campaign.id, prospect_id=context.prospect.id,
                agent_name=AgentName.CONVERSE, prompt_version_id=context.prompt_version_id,
                verdict=DecisionVerdict.ESCALATE,
                reasoning="Empty inbound message — routed to a human.",
                details={"next_action": "human", "trigger": "reply"},
            )

        classification = self.classifier.classify(message)
        outcome = decide_on_reply(classification, message)

        return AgentDecision(
            campaign_id=context.campaign.id, prospect_id=context.prospect.id,
            agent_name=AgentName.CONVERSE, prompt_version_id=context.prompt_version_id,
            verdict=outcome.verdict,
            reasoning=f"{outcome.reason} (category: {classification.category}, "
                      f"confidence: {classification.confidence:.2f}, via {classification.method}).",
            details={
                "trigger": "reply",
                "category": classification.category,
                "sentiment": classification.sentiment,
                "confidence": classification.confidence,
                "classification_method": classification.method,
                "next_action": outcome.next_action,
                "target_stage": outcome.target_stage.value if outcome.target_stage else None,
                "suppress": outcome.suppress,
            },
        )

    def _handle_follow_up(self, context: AgentContext) -> AgentDecision:
        persona = self._resolve_persona(context)
        policy = persona.follow_up_policy if persona else FollowUpPolicy()
        importance = persona.importance if persona else 1.0

        outcome = decide_on_follow_up(
            contact_count=context.link.contact_count,
            last_contact_at=context.link.updated_at,
            policy=policy,
            importance=importance,
        )

        return AgentDecision(
            campaign_id=context.campaign.id, prospect_id=context.prospect.id,
            agent_name=AgentName.CONVERSE, prompt_version_id=context.prompt_version_id,
            verdict=outcome.verdict,
            reasoning=outcome.reason,
            details={
                "trigger": "follow_up",
                "next_action": outcome.next_action,
                "target_stage": outcome.target_stage.value if outcome.target_stage else None,
                "contact_count": context.link.contact_count,
                "max_attempts": policy.max_attempts,
            },
        )

    def _resolve_persona(self, context: AgentContext) -> Optional[Persona]:
        if context.link.persona_id:
            return next((p for p in context.personas if p.id == context.link.persona_id), None)
        return None