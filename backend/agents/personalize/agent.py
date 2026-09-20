"""The Personalize agent.

Pipeline:
  1. Channel selection    — deterministic priority walk (channel_selector.py).
  2. Timing               — deterministic; WAIT + scheduled_time if outside hours.
  3. Drafting             — template fill, else grounded LLM, else generic (drafting.py).
  4. Asset selection      — RAG over campaign assets, channel-attachability filtered.

Returns an AgentDecision only (verdict SEND or WAIT). It does not send anything
and does not schedule anything itself — the orchestrator turns SEND into a
connector call and WAIT+scheduled_time into an APScheduler job later.
"""
from __future__ import annotations

from typing import Optional

from agents.base import Agent, AgentContext
from agents.personalize.asset_selector import select_asset
from agents.personalize.channel_selector import select_channel
from agents.personalize.drafting import MessageDrafter, default_drafter
from core.models import AgentDecision, AgentName, CampaignAsset, DecisionVerdict, Persona


class PersonalizeAgent(Agent):
    def __init__(
        self,
        *,
        drafter: Optional[MessageDrafter] = None,
        assets: Optional[list[CampaignAsset]] = None,
    ) -> None:
        self.drafter = drafter or default_drafter()
        self.assets = assets or []

    def run(self, context: AgentContext) -> AgentDecision:
        persona = self._resolve_persona(context)
        context_type = "cold_open"  # orchestrator overrides to 'follow_up_N' when re-invoked for follow-ups

        # Step 1 + 2: channel + timing (respecting per-channel + campaign pace limits)
        choice = select_channel(
            context.campaign, persona,
            usage_today=context.usage_today, total_today=context.total_today,
        )
        if choice.channel is None:
            return AgentDecision(
                campaign_id=context.campaign.id, prospect_id=context.prospect.id,
                agent_name=AgentName.PERSONALIZE, prompt_version_id=context.prompt_version_id,
                verdict=DecisionVerdict.WAIT, reasoning=f"No sendable channel: {choice.reason}",
                details={"channel": None, "scheduled_time": None, "context_type": context_type},
            )

        # Step 3: draft (goal-aware — campaign goals shape the call-to-action)
        draft = self.drafter.draft(
            prospect=context.prospect, persona=persona, channel=choice.channel,
            context_type=context_type, research_reasoning=context.link.qualification_reasoning,
            goals=context.campaign.goals,
        )

        # Step 4: asset selection (best-matching, channel-attachable, may be None)
        query_text = " ".join(filter(None, [
            context.prospect.profile.headline, context.prospect.profile.company_name,
            context.link.qualification_reasoning,
        ]))
        asset_id = select_asset(query_text, self.assets, choice.channel) if self.assets else None
        attached_asset_ids = [asset_id] if asset_id else []

        verdict = DecisionVerdict.SEND if choice.send_now else DecisionVerdict.WAIT
        reasoning = (
            f"{'Send' if choice.send_now else 'Scheduled'} via {choice.channel.value} "
            f"(draft method: {draft.method}). {choice.reason}."
        )

        return AgentDecision(
            campaign_id=context.campaign.id, prospect_id=context.prospect.id,
            agent_name=AgentName.PERSONALIZE, prompt_version_id=context.prompt_version_id,
            verdict=verdict, reasoning=reasoning,
            details={
                "channel": choice.channel.value,
                "subject": draft.subject,
                "draft_message": draft.body,
                "draft_method": draft.method,
                "attached_asset_ids": attached_asset_ids,
                "scheduled_time": choice.scheduled_time,   # ISO UTC, drops into APScheduler later
                "context_type": context_type,
            },
        )

    def _resolve_persona(self, context: AgentContext) -> Optional[Persona]:
        if context.link.persona_id:
            return next((p for p in context.personas if p.id == context.link.persona_id), None)
        return None