"""Generative Edits: campaign health metrics + deterministic improvement
suggestions, computed from real data.

Two of the five tiles in the original design mockup (asset-level "overperform/
underperform" stats) have no backing data anywhere in this system — nothing
tracks which asset was attached to which send, so there's no way to know if
an asset "overperforms." Rather than fabricate those numbers, this module
only surfaces tiles/suggestions backed by data that actually exists:
conversation turns, funnel stage, escalations, and campaign config.

Every suggestion is a concrete, applicable diff against the same
UpdateCampaignRequest shape the PATCH /campaigns/{id} endpoint already
accepts, or a reference to an existing action endpoint (e.g.
research-discovered) — never free text a human has to interpret and
hand-translate into a config change themselves. This mirrors "agents decide,
orchestrator executes": the rule decides the exact change; nothing here
sends it anywhere on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from core.models import Campaign, CampaignProspectLink, ChannelPolicy
from core.models.base import FunnelStage

MIN_CHANNEL_SAMPLE = 5           # touches needed before a channel's reply rate means anything
REPLY_RATE_MARGIN = 1.5          # "meaningfully better" = at least 1.5x another channel's rate
STALE_DISCOVERED_THRESHOLD = 3   # suggest a research pass once this many are stuck
ESCALATION_COUNT_THRESHOLD = 3
ESCALATION_RATE_THRESHOLD = 0.25
THRESHOLD_STEP = 10.0
THRESHOLD_CAP = 95.0


@dataclass
class CampaignEditMetrics:
    """The tiles shown at the top of a campaign's Generative Edits card."""
    conversions: int                            # prospects that reached 'opportunity'
    best_channel: Optional[str]                 # None if no channel has enough sample yet
    best_channel_reply_rate: Optional[float]     # 0-1
    open_escalations: int
    stale_discovered: int                        # 'discovered' prospects never researched


@dataclass
class Suggestion:
    id: str
    title: str
    reasoning: str
    kind: Literal["config_diff", "action"]
    diff: Optional[dict[str, Any]] = None        # partial UpdateCampaignRequest body, for kind="config_diff"
    action: Optional[str] = None                 # endpoint key the frontend dispatches to, for kind="action"


def _reply_rates(turns_by_channel: dict[str, dict[str, int]]) -> dict[str, float]:
    rates = {}
    for channel, counts in turns_by_channel.items():
        outbound = counts.get("outbound", 0)
        if outbound >= MIN_CHANNEL_SAMPLE:
            rates[channel] = counts.get("inbound", 0) / outbound
    return rates


def compute_campaign_metrics(
    links: list[CampaignProspectLink],
    turns_by_channel: dict[str, dict[str, int]],
    open_escalations: int,
) -> CampaignEditMetrics:
    conversions = sum(1 for l in links if l.stage == FunnelStage.OPPORTUNITY)
    stale_discovered = sum(1 for l in links if l.stage == FunnelStage.DISCOVERED)

    rates = _reply_rates(turns_by_channel)
    best_channel, best_rate = (max(rates.items(), key=lambda kv: kv[1]) if rates else (None, None))

    return CampaignEditMetrics(
        conversions=conversions,
        best_channel=best_channel,
        best_channel_reply_rate=round(best_rate, 3) if best_rate is not None else None,
        open_escalations=open_escalations,
        stale_discovered=stale_discovered,
    )


def generate_suggestions(
    campaign: Campaign,
    links: list[CampaignProspectLink],
    turns_by_channel: dict[str, dict[str, int]],
    open_escalations: int,
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []

    # --- Rule 1: prospects stuck at 'discovered', never researched ---------
    stale = sum(1 for l in links if l.stage == FunnelStage.DISCOVERED)
    if stale >= STALE_DISCOVERED_THRESHOLD:
        suggestions.append(Suggestion(
            id=f"{campaign.id}-stale-discovered",
            title=f"Research {stale} prospect(s) stuck at Discovered",
            reasoning=(
                f"{stale} prospects have been sitting at 'discovered' with no Research pass run on "
                "them — qualification, personalization, and outreach are all blocked until that happens."
            ),
            kind="action",
            action="research_discovered",
        ))

    # --- Rule 2: reallocate toward the meaningfully-better-performing channel
    rates = _reply_rates(turns_by_channel)
    if len(rates) >= 2:
        best_channel, best_rate = max(rates.items(), key=lambda kv: kv[1])
        worst_channel, worst_rate = min(rates.items(), key=lambda kv: kv[1])
        if worst_rate > 0 and best_rate >= worst_rate * REPLY_RATE_MARGIN and best_channel != worst_channel:
            policies = list(campaign.channel_policies)
            best_policy = next((p for p in policies if p.channel.value == best_channel), None)
            if best_policy is not None and best_policy.enabled and best_policy.daily_limit is not None:
                new_limit = max(best_policy.daily_limit + 1, round(best_policy.daily_limit * 1.5))
                new_policies = [
                    p.model_copy(update={"daily_limit": new_limit}) if p.channel.value == best_channel else p
                    for p in policies
                ]
                ratio = round(best_rate / worst_rate, 1) if worst_rate else None
                suggestions.append(Suggestion(
                    id=f"{campaign.id}-reallocate-{best_channel}",
                    title=f"{best_channel.capitalize()} is replying {ratio}× more than {worst_channel} — raise its daily limit",
                    reasoning=(
                        f"{best_channel.capitalize()} has a {best_rate:.0%} reply rate vs {worst_rate:.0%} on "
                        f"{worst_channel} (both with enough volume to compare). Raising {best_channel}'s daily "
                        f"limit from {best_policy.daily_limit} to {new_limit} shifts more outreach toward what's "
                        "actually working."
                    ),
                    kind="config_diff",
                    diff={"channel_policies": [p.model_dump(mode="json") for p in new_policies]},
                ))

    # --- Rule 3: high escalation load -> tighten the qualification bar -----
    contacted_or_later = sum(
        1 for l in links
        if l.stage not in (FunnelStage.DISCOVERED, FunnelStage.RESEARCHED, FunnelStage.QUALIFIED, FunnelStage.REJECTED)
    )
    escalation_rate = (open_escalations / contacted_or_later) if contacted_or_later else 0.0
    if open_escalations >= ESCALATION_COUNT_THRESHOLD and escalation_rate > ESCALATION_RATE_THRESHOLD:
        research_settings = campaign.agent_settings.get("research")
        current_threshold = (research_settings.decision_threshold if research_settings and research_settings.decision_threshold else 70.0)
        new_threshold = min(current_threshold + THRESHOLD_STEP, THRESHOLD_CAP)
        if new_threshold > current_threshold:
            new_agent_settings = {k: v.model_dump(mode="json") for k, v in campaign.agent_settings.items()}
            existing = new_agent_settings.get("research", {"enabled": True, "tools_allowed": []})
            existing["decision_threshold"] = new_threshold
            new_agent_settings["research"] = existing
            suggestions.append(Suggestion(
                id=f"{campaign.id}-tighten-threshold",
                title=f"{open_escalations} open escalations — raise the qualification bar",
                reasoning=(
                    f"{open_escalations} open escalations against {contacted_or_later} contacted-or-later "
                    f"prospects ({escalation_rate:.0%}) — a high rate often means under-qualified leads are "
                    f"reaching conversations they aren't ready for. Raising Research's qualification threshold "
                    f"from {current_threshold:.0f} to {new_threshold:.0f} filters more aggressively before "
                    "outreach starts."
                ),
                kind="config_diff",
                diff={"agent_settings": new_agent_settings},
            ))

    return suggestions