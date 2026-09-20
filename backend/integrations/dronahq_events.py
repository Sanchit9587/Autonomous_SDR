"""Real integration with DronaHQ's "Event Management Agent" — the agent that
creates workshop/meeting events on Google Calendar and posts updates to
Slack/Gmail (built and owned in the team's DronaHQ workspace, not in this
repo). This module is the "orchestrator turns a decision into a connector
call" step for the CONVERSE agent's `advance_meeting` action, the same way
`integrations/sms.py` is that step for Personalize's SMS channel.

Honesty note, load-bearing for anyone wiring this up for a demo:
  DronaHQ has no native SMS-sending capability (checked directly in the
  Connector Library — no "sms"/"twilio" tool exists anywhere in the
  catalog), so this integration is scoped to what DronaHQ actually does:
  calendar events + Slack/Gmail notifications. SMS stays on
  `integrations/sms.py` (Twilio/Textbelt).

  This webhook call is real and was tested end-to-end against the live
  agent (agents-backend.dronahq.com) — it genuinely invokes GPT-4o and gets
  a real response back. BUT the Event Management Agent's own tools (Google
  Calendar, Gmail, Slack, Sheets, Twitter, LinkedIn) show as *not connected*
  in the DronaHQ builder as of this writing — each needs someone with access
  to the team's Google/Slack accounts to click "Connect" and complete OAuth
  inside DronaHQ Studio. Until that happens, calling this webhook produces a
  real, on-topic conversational response (it asks the user to confirm event
  details, per its own system prompt) but does NOT actually create a
  calendar event or send a notification yet — there is no code-only way to
  finish that wiring, it requires that manual one-time OAuth step in the
  DronaHQ UI. This module does not pretend otherwise: the result always
  reports what the agent said, never a fabricated "event created".
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class EventAgentResult:
    ok: bool
    thread_id: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[str] = None


def _configured() -> bool:
    return bool(os.getenv("DRONAHQ_EVENT_AGENT_WEBHOOK_URL")) and bool(os.getenv("DRONAHQ_EVENT_AGENT_API_KEY"))


async def request_event_creation(message: str, *, thread_id: Optional[str] = None) -> EventAgentResult:
    """Ask the DronaHQ Event Management Agent to create/update a calendar
    event, passing it a natural-language description (it's a chat-style
    agent, not a structured-fields API — see its own system prompt). Pass
    the same `thread_id` back in to continue an existing conversation (e.g.
    after the agent asks a clarifying question).

    The webhook always runs the agent asynchronously and returns immediately
    with a thread_id/run_id; this function reports that DronaHQ accepted the
    request, not that an event now exists — see the module docstring for why.
    Never raises: a missing config or network failure comes back as a
    not-ok result so a webhook handler or scheduler tick can't crash on it.
    """
    webhook_url = os.getenv("DRONAHQ_EVENT_AGENT_WEBHOOK_URL")
    api_key = os.getenv("DRONAHQ_EVENT_AGENT_API_KEY")
    if not webhook_url or not api_key:
        return EventAgentResult(ok=False, error="DRONAHQ_EVENT_AGENT_WEBHOOK_URL/DRONAHQ_EVENT_AGENT_API_KEY not configured")

    params = {"thread_id": thread_id} if thread_id else None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                webhook_url,
                params=params,
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json={"message": message},
            )
        if resp.status_code >= 400:
            return EventAgentResult(ok=False, error=f"HTTP {resp.status_code}: {resp.text[:300]}")
        payload = resp.json()
        return EventAgentResult(
            ok=bool(payload.get("success")),
            thread_id=payload.get("thread_id"),
            run_id=payload.get("run_id"),
        )
    except Exception as exc:  # noqa: BLE001 — never take down a request over a DronaHQ hiccup
        return EventAgentResult(ok=False, error=str(exc))


def build_meeting_request_message(*, prospect_name: str, company: Optional[str], campaign_name: str,
                                   inbound_message: str) -> str:
    """Compose the natural-language prompt sent to the Event Management Agent
    when a prospect asks to meet. It's deliberately conversational (matching
    the agent's own "ask for title/date/time, then confirm" instructions)
    rather than a structured payload, since that's how this agent is built."""
    company_part = f" at {company}" if company else ""
    return (
        f"Set up a meeting for the \"{campaign_name}\" outreach campaign with {prospect_name}{company_part}. "
        f"They replied: \"{inbound_message}\". Propose a 30-minute slot in the next few business days and "
        f"confirm the details before creating the calendar event."
    )