"""Orchestration service layer.

The converse/follow-up orchestration lives here, not inside the HTTP handler, so
that BOTH the API endpoint and the scheduler can invoke the exact same logic.
"Agents decide, orchestrator executes" — this module is the "executes" part,
callable with a session from any caller (HTTP request or a scheduled job).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import AgentContext
from agents.converse.agent import ConverseAgent
from agents.personalize.agent import PersonalizeAgent
from core.db import repository as repo
from core.models import (
    AgentDecision,
    Campaign,
    CampaignProspectLink,
    CampaignStatus,
    Channel,
    ConversationTurn,
    Direction,
    FunnelStage,
    Prospect,
)
from integrations.dronahq_events import build_meeting_request_message, request_event_creation
from orchestrator import state_machine as sm

converse_agent = ConverseAgent()


async def process_converse(
    session: AsyncSession,
    campaign: Campaign,
    link: CampaignProspectLink,
    prospect: Prospect,
    *,
    trigger: str,
    inbound_message: Optional[str] = None,
    channel: Channel = Channel.EMAIL,
) -> dict:
    """Run Converse and apply its decision (record turn, suppress, transition,
    loop back to Personalize). Shared by the API endpoint and the scheduler."""
    personas = await repo.list_personas_for_campaign(session, campaign.id)
    history = await repo.list_turns_for_prospect(session, campaign.id, link.prospect_id)

    if trigger == "reply" and inbound_message:
        await repo.append_turn(session, ConversationTurn(
            campaign_id=campaign.id, prospect_id=link.prospect_id,
            channel=channel, direction=Direction.INBOUND, content=inbound_message,
        ))

    context = AgentContext(
        campaign=campaign, prospect=prospect, link=link, personas=personas,
        trigger=trigger, inbound_message=inbound_message, conversation_history=history,
    )
    decision = converse_agent.run(context)
    await repo.append_decision(session, decision)

    follow_up_draft: Optional[AgentDecision] = None

    if decision.details.get("suppress"):
        for key in (prospect.profile.linkedin_url, prospect.profile.work_email, prospect.profile.name):
            if key:
                await repo.add_suppression(session, key)

    target_stage = decision.details.get("target_stage")
    if target_stage:
        try:
            sm.transition(link, FunnelStage(target_stage), campaign)
        except (sm.InvalidTransitionError, sm.CampaignNotLiveError):
            pass
    await repo.save_link(session, link)

    next_action = decision.details.get("next_action")
    if next_action in ("reply", "follow_up") and link.stage == FunnelStage.ENGAGED:
        assets = await repo.list_assets_for_campaign(session, campaign.id)
        p_agent = PersonalizeAgent(assets=assets)
        p_decision = p_agent.run(context)
        await repo.append_decision(session, p_decision)
        follow_up_draft = p_decision

    event_management_result: Optional[dict] = None
    if next_action == "advance_meeting":
        event_management_result = await request_calendar_event(
            session, campaign=campaign, prospect=prospect, inbound_message=inbound_message or "",
        )

    return {"decision": decision, "personalize_followup": follow_up_draft, "event_management_result": event_management_result}


async def request_calendar_event(
    session: AsyncSession, *, campaign: Campaign, prospect: Prospect, inbound_message: str,
) -> dict:
    """Called when Converse's policy fires `advance_meeting` (a prospect asked
    to meet). Hands off to DronaHQ's Event Management Agent — see
    integrations/dronahq_events.py for exactly what that does and does not
    do today (it's a real, tested webhook call; the calendar/notification
    tools behind it still need someone to authorize them in DronaHQ Studio).
    Records the agent's reply as a conversation turn either way, so it shows
    up in the dashboard instead of disappearing silently.
    """
    message = build_meeting_request_message(
        prospect_name=prospect.profile.name, company=prospect.profile.company_name,
        campaign_name=campaign.name, inbound_message=inbound_message,
    )
    result = await request_event_creation(message)

    note = (
        f"[DronaHQ Event Management Agent] request sent (thread {result.thread_id})"
        if result.ok else f"[DronaHQ Event Management Agent] request failed: {result.error}"
    )
    await repo.append_turn(session, ConversationTurn(
        campaign_id=campaign.id, prospect_id=prospect.id,
        channel=Channel.EMAIL, direction=Direction.OUTBOUND,
        content=note, agent_name="dronahq_event_management",
    ))
    return {"ok": result.ok, "thread_id": result.thread_id, "run_id": result.run_id, "error": result.error}


async def fire_follow_up(session: AsyncSession, campaign_id: str, link_id: str) -> dict:
    """Called by the scheduler when a follow-up timer fires. Encodes the pause /
    idempotency rules we agreed on:

      * campaign paused   -> park it (follow_up_owed=True), take no action; it
        fires on resume (now or next working window).
      * prospect already replied (ENGAGED+) or terminal -> no-op permanently.
      * otherwise         -> run the Converse follow-up path.
    """
    campaign = await repo.get_campaign(session, campaign_id)
    link = await repo.get_link(session, link_id)
    if campaign is None or link is None:
        return {"status": "gone"}  # campaign/prospect deleted since scheduling

    prospect = await repo.get_prospect(session, link.prospect_id)
    if prospect is None:
        return {"status": "gone"}

    # Terminal / already-progressed prospects: nothing to follow up on.
    if link.stage in (FunnelStage.REJECTED, FunnelStage.OPPORTUNITY, FunnelStage.MEETING,
                      FunnelStage.ENGAGED, FunnelStage.QUALIFIED, FunnelStage.DISCOVERED):
        # Follow-ups only make sense after we've contacted them and gone quiet.
        if link.stage != FunnelStage.CONTACTED:
            link.follow_up_owed = False
            link.next_follow_up_at = None
            await repo.save_link(session, link)
            return {"status": "skipped", "reason": f"stage={link.stage.value}"}

    # Suppressed since scheduling?
    for key in (prospect.profile.linkedin_url, prospect.profile.work_email, prospect.profile.name):
        if key and await repo.is_suppressed(session, key):
            link.follow_up_owed = False
            await repo.save_link(session, link)
            return {"status": "skipped", "reason": "suppressed"}

    # Campaign paused -> park as owed, act on resume.
    if campaign.status != CampaignStatus.LIVE:
        link.follow_up_owed = True
        await repo.save_link(session, link)
        return {"status": "parked", "reason": f"campaign {campaign.status.value}"}

    # Live: run the follow-up. Clear the owed flag first.
    link.follow_up_owed = False
    link.next_follow_up_at = None
    await repo.save_link(session, link)
    result = await process_converse(session, campaign, link, prospect, trigger="follow_up")
    return {"status": "fired", **{k: v for k, v in result.items()}}