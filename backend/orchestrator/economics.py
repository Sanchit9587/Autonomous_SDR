"""Campaign unit economics: CAC and LTV, minimal version.

Deliberately simple, matching what the platform actually tracks today:
  - Cost (CAC's numerator): configured cost-per-mille (ChannelPolicy.cpm) times
    how many outbound touches actually went out on that channel, summed across
    channels. A channel with no cpm configured costs $0 — we don't invent a
    number for it.
  - Revenue (LTV): a manager-entered deal_value on CampaignProspectLink. There
    is no automatic revenue signal anywhere in the system, so this is the
    average of whatever deal values have actually been entered so far.

Both figures are None (shown as "—" in the UI) when there isn't enough data
yet to mean anything — a CAC of "$0.00" or an LTV of "$0.00" would be
misleading, not just incomplete.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.models import CampaignProspectLink, ChannelPolicy, FunnelStage


@dataclass
class CampaignEconomics:
    total_spend: float                     # $ spent on outbound touches so far
    opportunities: int                     # prospects that reached 'opportunity' stage
    deals_with_value: int                  # of those, how many have a deal_value entered
    avg_deal_value: Optional[float]        # None if no deal values entered yet
    cac: Optional[float]                   # None if there are no opportunities yet (would divide by zero)
    ltv_cac_ratio: Optional[float]         # None unless both avg_deal_value and cac exist


def compute_campaign_economics(
    channel_policies: list[ChannelPolicy],
    touches_per_channel: dict[str, int],
    links: list[CampaignProspectLink],
) -> CampaignEconomics:
    total_spend = 0.0
    for policy in channel_policies:
        if policy.cpm is None:
            continue
        touches = touches_per_channel.get(policy.channel.value, 0)
        total_spend += (policy.cpm / 1000.0) * touches

    opportunity_links = [l for l in links if l.stage == FunnelStage.OPPORTUNITY]
    valued = [l.deal_value for l in opportunity_links if l.deal_value is not None]

    avg_deal_value = (sum(valued) / len(valued)) if valued else None
    cac = (total_spend / len(opportunity_links)) if opportunity_links else None
    ltv_cac_ratio = (avg_deal_value / cac) if (avg_deal_value is not None and cac) else None

    return CampaignEconomics(
        total_spend=round(total_spend, 2),
        opportunities=len(opportunity_links),
        deals_with_value=len(valued),
        avg_deal_value=round(avg_deal_value, 2) if avg_deal_value is not None else None,
        cac=round(cac, 2) if cac is not None else None,
        ltv_cac_ratio=round(ltv_cac_ratio, 2) if ltv_cac_ratio is not None else None,
    )