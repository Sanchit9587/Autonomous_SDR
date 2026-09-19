"""Global suppression / do-not-contact list (PS: global suppression is a
platform-wide requirement, not per-campaign).

In-memory set for now, same as the other stores; swap for a DB table later
without changing callers. The orchestrator checks this before ANY outreach,
and the Converse agent's unsubscribe handling is what adds to it.
"""
from __future__ import annotations

from core.models import Prospect


class SuppressionList:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    @staticmethod
    def _key(value: str) -> str:
        return value.strip().lower()

    def add(self, value: str) -> None:
        if value:
            self._keys.add(self._key(value))

    def add_prospect(self, prospect: Prospect) -> None:
        """Suppress by every identifier we have, so a re-scraped duplicate of
        the same person (different id) is still caught."""
        for v in (prospect.profile.linkedin_url, prospect.profile.work_email, prospect.profile.name):
            if v:
                self.add(v)

    def contains(self, value: str) -> bool:
        return bool(value) and self._key(value) in self._keys

    def is_suppressed(self, prospect: Prospect) -> bool:
        for v in (prospect.profile.linkedin_url, prospect.profile.work_email, prospect.profile.name):
            if v and self.contains(v):
                return True
        return False

    def all(self) -> list[str]:
        return sorted(self._keys)