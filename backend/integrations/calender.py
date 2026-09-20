"""Google Calendar integration: creates the meeting event — with an
auto-generated Google Meet link — on the admin's calendar.

Auth: a Google service account with domain-wide delegation, so it can act
*as* the admin (impersonate their calendar) rather than needing each admin to
individually OAuth. See:
https://developers.google.com/identity/protocols/oauth2/service-account

Env vars:
  GOOGLE_SERVICE_ACCOUNT_JSON  -> either the service-account JSON itself, or a
                                   path to the JSON key file.

Dev fallback: if GOOGLE_SERVICE_ACCOUNT_JSON isn't set, this doesn't raise —
it logs what it *would* have created and returns a stub Meet link, so the
Converse -> meeting pipeline runs end to end without live Google credentials
(same "runs out of the box" pattern as auth/security.py's JWT_SECRET dev
fallback and rag/embeddings.py's TF-IDF default backend). Set the env var
above for a real calendar event + Meet link.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass
class MeetingEvent:
    event_id: str
    meet_link: str
    html_link: Optional[str]
    start: datetime
    end: datetime
    is_stub: bool = False  # True when created via the no-credentials dev fallback


def _extract_meet_link(event: dict) -> str:
    for ep in event.get("conferenceData", {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri", "")
    return event.get("hangoutLink", "")


class GoogleCalendarClient:
    """Thin wrapper around Calendar API's events.insert with conferenceData,
    scoped to whichever admin calendar the service account is asked to act as."""

    def __init__(self, *, service_account_json: Optional[str] = None) -> None:
        self._service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    def is_configured(self) -> bool:
        return bool(self._service_account_json)

    def _build_service(self, subject: str):
        # Imported lazily so the module (and the dev stub path) works even in
        # environments that don't have google-api-python-client installed.
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        raw = self._service_account_json.strip()
        info = json.loads(raw) if raw.startswith("{") else json.loads(open(raw, encoding="utf-8").read())
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        delegated = creds.with_subject(subject)  # domain-wide delegation: act as the admin
        return build("calendar", "v3", credentials=delegated, cache_discovery=False)

    def create_meeting_event(
        self,
        *,
        admin_email: str,
        participant_email: str,
        participant_name: str,
        summary: str,
        description: str,
        start: datetime,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
    ) -> MeetingEvent:
        end = start + timedelta(minutes=duration_minutes)

        if not self.is_configured():
            stub_id = uuid.uuid4().hex[:10]
            logger.warning(
                "GOOGLE_SERVICE_ACCOUNT_JSON not set — creating a STUB calendar event for "
                "%s on %s's calendar (no real Google Calendar API call made). "
                "Set GOOGLE_SERVICE_ACCOUNT_JSON to create real events with a real Meet link.",
                participant_email, admin_email,
            )
            return MeetingEvent(
                event_id=f"stub_{stub_id}",
                meet_link=f"https://meet.google.com/{stub_id[:3]}-{stub_id[3:7]}-{stub_id[7:10]}",
                html_link=None,
                start=start, end=end, is_stub=True,
            )

        service = self._build_service(admin_email)
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "attendees": [
                {"email": admin_email},
                {"email": participant_email, "displayName": participant_name},
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "email", "minutes": 60}, {"method": "popup", "minutes": 10}],
            },
        }
        event = service.events().insert(
            calendarId=calendar_id, body=body, conferenceDataVersion=1, sendUpdates="all",
        ).execute()

        return MeetingEvent(
            event_id=event["id"],
            meet_link=_extract_meet_link(event),
            html_link=event.get("htmlLink"),
            start=start, end=end, is_stub=False,
        )


_default_client: Optional[GoogleCalendarClient] = None


def default_client() -> GoogleCalendarClient:
    global _default_client
    if _default_client is None:
        _default_client = GoogleCalendarClient()
    return _default_client