"""Deterministic channel selection + send timing. No ML: this is priority-list
walking and datetime comparison, which is faster, free, and more auditable
than asking a model 'which channel should I use?'.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from core.models import Campaign, Channel, ChannelPolicy, Persona


@dataclass
class ChannelChoice:
    channel: Optional[Channel]
    send_now: bool
    scheduled_time: Optional[str]        # ISO UTC timestamp when send_now is False
    reason: str


def _policy_for(campaign: Campaign, channel: Channel) -> Optional[ChannelPolicy]:
    return next((p for p in campaign.channel_policies if p.channel == channel), None)


def _parse_working_hours(working_hours: Optional[str]) -> Optional[tuple[time, time]]:
    """Parse 'HH:MM-HH:MM' (timezone suffix ignored for the hackathon — treated
    as UTC). Returns None if unparseable, meaning 'no restriction'."""
    if not working_hours:
        return None
    try:
        window = working_hours.split()[0]  # drop any trailing tz label like 'IST'
        start_s, end_s = window.split("-")
        sh, sm = map(int, start_s.split(":"))
        eh, em = map(int, end_s.split(":"))
        return time(sh, sm), time(eh, em)
    except Exception:
        return None


def _next_window_start(now: datetime, start: time) -> str:
    candidate = now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate.isoformat()


def select_channel(
    campaign: Campaign,
    persona: Optional[Persona],
    *,
    usage_today: Optional[dict[str, int]] = None,
    total_today: int = 0,
    now: Optional[datetime] = None,
) -> ChannelChoice:
    """Walk the effective channel priority; pick the first channel that is
    enabled, under its daily limit, and within working hours. If a channel is
    the best pick but outside its hours, return it with a scheduled_time for
    the next window open instead of send_now.

    Respects two limits, both fed from actual sent-touch counts:
      * per-channel `daily_limit` (skip that channel if hit today)
      * campaign-wide `pace_per_day` (defer everything to tomorrow if hit)
    """
    now = now or datetime.now(timezone.utc)
    usage_today = usage_today or {}

    # Campaign-wide pace cap: if today's total touches already hit the pace,
    # nothing more goes out today — defer to the start of tomorrow.
    if campaign.pace_per_day is not None and total_today >= campaign.pace_per_day:
        tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return ChannelChoice(
            channel=None, send_now=False, scheduled_time=tomorrow.isoformat(),
            reason=f"daily pace reached ({total_today}/{campaign.pace_per_day}) — deferring to tomorrow",
        )

    default_order = campaign.default_channel_priority or [p.channel for p in campaign.channel_policies]
    order = persona.effective_channel_priority(default_order) if persona else default_order

    if not order:
        return ChannelChoice(channel=None, send_now=False, scheduled_time=None, reason="no channels configured")

    deferred: Optional[ChannelChoice] = None

    for channel in order:
        policy = _policy_for(campaign, channel)
        if policy is not None and not policy.enabled:
            continue  # channel switched off -> reroute to next enabled channel
        if policy is not None and policy.daily_limit is not None:
            if usage_today.get(channel.value, 0) >= policy.daily_limit:
                continue  # over this channel's limit today, try next channel

        hours = _parse_working_hours(policy.working_hours) if policy else None
        if hours is not None:
            start, end = hours
            if not (start <= now.time() <= end):
                # This channel is the best available but outside its window —
                # remember it as a fallback deferral, keep looking for one we
                # can send on right now.
                if deferred is None:
                    deferred = ChannelChoice(
                        channel=channel, send_now=False,
                        scheduled_time=_next_window_start(now, start),
                        reason=f"{channel.value} outside working hours {policy.working_hours}",
                    )
                continue

        return ChannelChoice(channel=channel, send_now=True, scheduled_time=None, reason=f"selected {channel.value}")

    if deferred is not None:
        return deferred
    return ChannelChoice(channel=None, send_now=False, scheduled_time=None, reason="all channels disabled or over daily limit")