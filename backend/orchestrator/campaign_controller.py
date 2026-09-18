"""Campaign lifecycle control (PS section 3: Campaign Control, Levels of Operational Control).

Pure functions on Campaign objects — no DB yet. The API layer (api.py) wires these
to an in-memory store for now; swap in real persistence later without touching this file.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Optional

from core.models import Campaign, CampaignStatus
from core.models.base import _new_id

_ALLOWED_STATUS_TRANSITIONS: dict[CampaignStatus, set[CampaignStatus]] = {
    CampaignStatus.DRAFT: {CampaignStatus.LIVE, CampaignStatus.ARCHIVED},
    CampaignStatus.LIVE: {CampaignStatus.PAUSED, CampaignStatus.COMPLETED},
    CampaignStatus.PAUSED: {CampaignStatus.LIVE, CampaignStatus.COMPLETED, CampaignStatus.ARCHIVED},
    CampaignStatus.COMPLETED: {CampaignStatus.ARCHIVED},
    CampaignStatus.ARCHIVED: set(),
}


class InvalidCampaignStatusTransitionError(Exception):
    pass


def _set_status(campaign: Campaign, to_status: CampaignStatus) -> Campaign:
    if to_status not in _ALLOWED_STATUS_TRANSITIONS.get(campaign.status, set()):
        raise InvalidCampaignStatusTransitionError(
            f"Cannot move campaign {campaign.id} from {campaign.status} to {to_status}; "
            f"allowed: {sorted(_ALLOWED_STATUS_TRANSITIONS.get(campaign.status, set()))}"
        )
    campaign.status = to_status
    return campaign


def activate(campaign: Campaign) -> Campaign:
    """Draft -> Live. Agents may now discover, research, qualify and contact prospects."""
    return _set_status(campaign, CampaignStatus.LIVE)


def pause(campaign: Campaign) -> Campaign:
    """Live -> Paused. All autonomous execution stops immediately; data is retained;
    no new outreach fires. Does not affect any other campaign."""
    return _set_status(campaign, CampaignStatus.PAUSED)


def resume(campaign: Campaign) -> Campaign:
    """Paused -> Live."""
    return _set_status(campaign, CampaignStatus.LIVE)


def complete(campaign: Campaign) -> Campaign:
    """Live/Paused -> Completed. History and analytics remain fully available."""
    return _set_status(campaign, CampaignStatus.COMPLETED)


def archive(campaign: Campaign) -> Campaign:
    return _set_status(campaign, CampaignStatus.ARCHIVED)


def duplicate(campaign: Campaign, *, new_name: Optional[str] = None) -> Campaign:
    """Clone a campaign's configuration into a fresh Draft — used for A/B variants
    (PS section 3, Duplication & Experimentation stretch goal)."""
    clone = deepcopy(campaign)
    clone.id = _new_id("camp")
    clone.name = new_name or f"{campaign.name} (copy)"
    clone.status = CampaignStatus.DRAFT
    return clone


class GlobalKillSwitch:
    """PS section 3, Levels of Operational Control: a platform-wide stop.

    Kept as a tiny in-memory flag here; the API layer checks this before letting
    ANY campaign move prospects into outreach stages, regardless of that
    campaign's own status. In production this would be a single row in a fast
    key-value store (Redis) so every service instance sees it instantly.
    """

    def __init__(self) -> None:
        self._engaged: bool = False

    def engage(self) -> None:
        self._engaged = True

    def disengage(self) -> None:
        self._engaged = False

    @property
    def is_engaged(self) -> bool:
        return self._engaged