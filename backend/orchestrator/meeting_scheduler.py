"""Books the meeting once Converse decides a prospect wants one.

Called from orchestrator.service.process_converse when Converse's next_action
is "advance_meeting" (see agents/converse/policy.py's "meeting_request"
outcome). Creates a Google Calendar event — with an auto-generated Google
Meet link — on the admin's calendar, emails the participant that link plus a
reminder, and records both on the CampaignProspectLink (so the Prospects view
can show it) and as an outbound ConversationTurn (so it shows up in the
conversation history / decision trace like any other touch).

"Agents decide, orchestrator executes": Converse only decided the prospect
wants to meet — this module is the "executes" part for that outcome, the same
role orchestrator/service.py already plays for replies and follow-ups.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.db import repository as repo
from core.models import Campaign, CampaignProspectLink, Channel, ConversationTurn, Direction, Prospect, UserRole
from integrations.calendar import default_client as default_calendar_client
from integrations.mailer import default_sender as default_email_sender

# How far out (in business days) and at what hour UTC the default slot lands.
# A human can always move it in Google Calendar afterwards — the goal here is
# getting an invite out immediately rather than blocking on someone picking a time.
DEFAULT_LEAD_DAYS = int(os.getenv("MEETING_DEFAULT_LEAD_DAYS", "1"))
DEFAULT_HOUR_UTC = int(os.getenv("MEETING_DEFAULT_HOUR_UTC", "15"))
DEFAULT_DURATION_MINUTES = int(os.getenv("MEETING_DURATION_MINUTES", "30"))


def _next_slot(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    candidate = now
    days_added = 0
    while days_added < DEFAULT_LEAD_DAYS:
        candidate += timedelta(days=1)
        if candidate.weekday() < 5:  # Mon-Fri only
            days_added += 1
    return candidate.replace(hour=DEFAULT_HOUR_UTC, minute=0, second=0, microsecond=0)


async def _resolve_admin(session: AsyncSession, campaign: Campaign) -> dict:
    """Whose calendar the event goes on. Priority:
    ADMIN_CALENDAR_EMAIL env override -> an ADMIN-role user -> the campaign owner."""
    override = os.getenv("ADMIN_CALENDAR_EMAIL")
    if override:
        return {"email": override, "name": os.getenv("ADMIN_CALENDAR_NAME", "Admin")}

    users = await repo.list_users(session)
    admin = next((u for u in users if u.role == UserRole.ADMIN and u.is_active), None)
    if admin:
        return {"email": admin.email, "name": admin.full_name or "Admin"}

    return {"email": campaign.owner, "name": "Admin"}


async def schedule_meeting(
    session: AsyncSession,
    campaign: Campaign,
    link: CampaignProspectLink,
    prospect: Prospect,
) -> dict:
    """Create the calendar event + send the participant email. Mutates `link`
    in place with the booking details (caller is responsible for persisting
    it, same as every other orchestrator.service mutation)."""
    participant_email = prospect.profile.work_email
    admin = await _resolve_admin(session, campaign)

    if not participant_email:
        return {
            "status": "skipped",
            "reason": "prospect has no work_email on file — nothing to send the invite to",
            "admin_email": admin["email"],
        }

    start = _next_slot()
    summary = f"{campaign.name} — intro call with {prospect.profile.name}"
    description = (
        f"Booked automatically by the Converse agent after {prospect.profile.name} "
        f"asked to meet in campaign \"{campaign.name}\"."
    )

    calendar_event = default_calendar_client().create_meeting_event(
        admin_email=admin["email"],
        participant_email=participant_email,
        participant_name=prospect.profile.name,
        summary=summary,
        description=description,
        start=start,
        duration_minutes=DEFAULT_DURATION_MINUTES,
    )

    email_result = default_email_sender().send_meeting_invite(
        to_email=participant_email,
        to_name=prospect.profile.name,
        meet_link=calendar_event.meet_link,
        start=calendar_event.start,
        end=calendar_event.end,
        admin_name=admin["name"],
        admin_email=admin["email"],
        campaign_name=campaign.name,
    )

    link.meeting_link = calendar_event.meet_link
    link.meeting_scheduled_at = calendar_event.start.isoformat()
    link.calendar_event_id = calendar_event.event_id

    await repo.append_turn(session, ConversationTurn(
        campaign_id=campaign.id,
        prospect_id=prospect.id,
        channel=Channel.EMAIL,
        direction=Direction.OUTBOUND,
        agent_name="converse",
        content=(
            f"Meeting invite sent to {participant_email} — Google Meet link {calendar_event.meet_link}, "
            f"{calendar_event.start.strftime('%Y-%m-%d %H:%M UTC')} "
            f"(calendar event added on {admin['email']}'s calendar)."
        ),
    ))

    return {
        "status": "booked",
        "meet_link": calendar_event.meet_link,
        "scheduled_at": calendar_event.start.isoformat(),
        "duration_minutes": DEFAULT_DURATION_MINUTES,
        "calendar_event_id": calendar_event.event_id,
        "calendar_is_stub": calendar_event.is_stub,
        "email_sent": email_result.sent,
        "email_is_stub": email_result.is_stub,
        "admin_email": admin["email"],
        "participant_email": participant_email,
    }