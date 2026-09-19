"""CampaignAsset: media/collateral available to the Personalize agent.

Campaign-scoped, not persona-scoped — a poster or case study can suit more
than one persona. Personalize retrieves against `description`/`tags` the same
way it retrieves knowledge-base examples, then decides whether the chosen
channel can actually carry it (SMS realistically only carries a link).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models.base import AssetType, TimestampedModel, _new_id


class CampaignAsset(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("asset"))
    campaign_id: str
    name: str
    asset_type: AssetType
    url: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    def is_attachable_on(self, channel_value: str) -> bool:
        """SMS can only carry a link; every other channel can carry anything."""
        if channel_value == "sms":
            return self.asset_type in (AssetType.LINK,)
        return True