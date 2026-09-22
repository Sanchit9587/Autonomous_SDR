"""Seed realistic DEMO data so the dashboards look full for a recording.

Run from backend/:
    python -m scripts.seed_demo          # create demo campaigns + data
    python -m scripts.seed_demo --wipe   # remove ONLY the demo data again

What it creates (everything the dashboard cards read from):
  * 3 campaigns tagged "DEMO · ..." with different ICPs and statuses
    (Live / Paused / Live) — satisfies the "3 concurrent campaigns" story.
  * channel policies WITH cpm set (so "Spend so far" / CAC are non-zero).
  * a couple of personas per campaign.
  * ~24 prospects per campaign spread across every funnel stage, incl. some
    rejected and some at 'opportunity' with deal_value set (so CAC, Avg deal
    value, and LTV:CAC all compute).
  * outbound + inbound ConversationTurns (drive spend via count_touches_total
    and give Live Activity / reply signals content).
  * AgentDecisions across research/personalize/converse, including several
    'escalate' verdicts (so the Escalations queue isn't empty).
  * assigns Mark (rep) to each campaign so his rep app is populated too.

Only uses repository/engine functions that exist in the current code. It does
NOT create users — it looks up ava@sdrhq.io / mark@sdrhq.io; if they're missing
it tells you to run scripts.seed_users first (so we never guess the password hash).

Idempotent-ish: re-running creates fresh demo campaigns each time (new ids).
Use --wipe to clear previous demo data first if you want a clean slate.
"""
from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import delete, select

from core.db import repository as repo
from core.db import tables as t
from core.db.engine import SessionLocal
from core.models import (
    AgentDecision,
    Campaign,
    CampaignProspectLink,
    ChannelPolicy,
    ConversationTurn,
    Direction,
    Persona,
    Prospect,
    ProspectProfile,
)
from core.models.base import (
    AgentName,
    CampaignStatus,
    Channel,
    ChannelMode,
    DecisionVerdict,
    FunnelStage,
)

load_dotenv()

DEMO_PREFIX = "DEMO · "
random.seed(42)  # deterministic demo data

# --- campaign blueprints -----------------------------------------------------
_CAMPAIGNS = [
    {
        "name": "US SaaS CTO Outreach",
        "status": CampaignStatus.LIVE,
        "vision": "Win US mid-market SaaS engineering leaders with a technical, ROI-forward story.",
        "roles": ["CTO", "VP Engineering"], "geo": ["United States"], "keywords": "SaaS infrastructure",
        "goals": ["book_meeting", "signup"],
        "policies": [
            ChannelPolicy(channel=Channel.EMAIL, enabled=True, mode=ChannelMode.AUTOMATE, cpm=1800.0, daily_limit=50),
            ChannelPolicy(channel=Channel.LINKEDIN, enabled=True, mode=ChannelMode.APPROVAL, cpm=3500.0, daily_limit=25),
        ],
        "personas": [
            ("Technical Founder", "hands-on technical founder building infrastructure and platform engineering"),
            ("Economic Buyer", "budget owner focused on ROI, procurement, and vendor evaluation"),
        ],
        "companies": ["Acme Cloud", "DataForge", "LedgerPro", "BrightMetrics", "FinEdge", "Nimbus Systems", "Corevault", "Quanta Labs"],
    },
    {
        "name": "India BFSI CIO",
        "status": CampaignStatus.PAUSED,
        "vision": "Reach Indian banking & financial-services CIOs with a compliance-first message.",
        "roles": ["CIO", "Head of IT"], "geo": ["India"], "keywords": "BFSI compliance security",
        "goals": ["book_meeting"],
        "policies": [
            ChannelPolicy(channel=Channel.EMAIL, enabled=True, mode=ChannelMode.APPROVAL, cpm=1500.0, daily_limit=40),
            ChannelPolicy(channel=Channel.SMS, enabled=True, mode=ChannelMode.MANUAL, cpm=2200.0, daily_limit=20),
        ],
        "personas": [
            ("Compliance-first CIO", "risk-averse CIO in banking, cares about audit, RBI compliance, data residency"),
        ],
        "companies": ["FinBank", "SecureTrust", "RupeeWorks", "MetroFin", "AxisNova", "CapitalOne India"],
    },
    {
        "name": "US Voice AI Founders",
        "status": CampaignStatus.LIVE,
        "vision": "Engage US voice-AI startup founders with a fast, founder-to-founder tone.",
        "roles": ["Founder", "CEO", "Co-founder"], "geo": ["United States"], "keywords": "Voice AI startup",
        "goals": ["book_meeting", "free_trial"],
        "policies": [
            ChannelPolicy(channel=Channel.EMAIL, enabled=True, mode=ChannelMode.AUTOMATE, cpm=1900.0, daily_limit=60),
            ChannelPolicy(channel=Channel.LINKEDIN, enabled=True, mode=ChannelMode.AUTOMATE, cpm=3200.0, daily_limit=30),
            ChannelPolicy(channel=Channel.VOICE, enabled=True, mode=ChannelMode.APPROVAL, cpm=9000.0, daily_limit=10),
        ],
        "personas": [
            ("Seed-stage Founder", "technical founder at a seed-stage voice AI startup, moves fast, hates fluff"),
            ("Growth-stage CEO", "CEO scaling a funded voice AI company, focused on GTM efficiency"),
        ],
        "companies": ["VoxAI", "SpeakEasy", "EchoStack", "Cadence AI", "Larynx", "ToneLoop", "Vocalis"],
    },
]

# How many prospects land in each stage (per campaign) — shaped like a real funnel.
_STAGE_DISTRIBUTION = [
    (FunnelStage.DISCOVERED, 4),
    (FunnelStage.RESEARCHED, 3),
    (FunnelStage.QUALIFIED, 4),
    (FunnelStage.REJECTED, 3),
    (FunnelStage.CONTACTED, 4),
    (FunnelStage.ENGAGED, 3),
    (FunnelStage.MEETING, 2),
    (FunnelStage.OPPORTUNITY, 3),
]

_FIRST = ["Jane", "Raj", "Mei", "Tom", "Sara", "David", "Priya", "Marco", "Lena", "Omar", "Nina", "Carl", "Ava", "Ken", "Rosa", "Ivan", "Tara", "Sam", "Leo", "Mia", "Zoe", "Ravi", "Gina", "Paul"]
_LAST = ["Doe", "Patel", "Lin", "Becker", "Okafor", "Ng", "Shah", "Turin", "Vogel", "Aziz", "Kraft", "Reyes", "Chen", "Park", "Diaz", "Volkov", "Rao", "Lee", "Moretti", "Wang"]


def _profile(company: str, role: str) -> ProspectProfile:
    first = random.choice(_FIRST)
    last = random.choice(_LAST)
    slug = f"{first}-{last}-{random.randint(100, 999)}".lower()
    return ProspectProfile(
        name=f"{first} {last}",
        linkedin_url=f"https://linkedin.com/in/{slug}",
        headline=f"{role} at {company}",
        location=random.choice(["San Francisco, US", "New York, US", "Austin, US", "Mumbai, India", "Bengaluru, India", "Boston, US"]),
        position=role,
        company_name=company,
        company_size=random.choice([60, 85, 120, 200, 340, 410, 500]),
        work_email=f"{first.lower()}@{company.replace(' ', '').lower()}.com",
        enrichment_status="ok",
    )


def _now_minus(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


async def _seed() -> None:
    async with SessionLocal() as session:
        # Look up the demo users (don't create — avoid guessing the password hash).
        ava = await repo.get_user_by_email(session, "ava@sdrhq.io")
        mark = await repo.get_user_by_email(session, "mark@sdrhq.io")
        if ava is None or mark is None:
            print("!! ava@sdrhq.io and/or mark@sdrhq.io not found in this DB.")
            print("   Run `python -m scripts.seed_users` first, then re-run this seeder.")
            return
        owner_id, rep_id = ava.id, mark.id

        touch_seq = 0
        for spec in _CAMPAIGNS:
            campaign = Campaign(
                name=DEMO_PREFIX + spec["name"],
                description="Seeded demo campaign.",
                vision_statement=spec["vision"],
                owner=owner_id,
                status=spec["status"],
                icp={"target_roles": spec["roles"], "geography": spec["geo"], "keywords": spec["keywords"],
                     "company_size_min": 50, "company_size_max": 500},
                agent_settings={"research": {"enabled": True, "decision_threshold": 65.0, "tools_allowed": []}},
                channel_policies=spec["policies"],
                default_channel_priority=[p.channel for p in spec["policies"]],
                budget=12000.0,
                start_date="2026-09-01",
                end_date="2026-11-15",
                target_scale=2000,
                pace_per_day=30,
                goals=spec["goals"],
                assigned_rep_ids=[rep_id],
            )
            await repo.save_campaign(session, campaign)

            personas: list[Persona] = []
            for pname, notes in spec["personas"]:
                p = Persona(campaign_id=campaign.id, name=pname, qualification_notes=notes,
                            importance=random.choice([1.0, 1.0, 2.0]))
                await repo.save_persona(session, p)
                personas.append(p)

            enabled_channels = [pol.channel for pol in spec["policies"] if pol.enabled]

            for stage, count in _STAGE_DISTRIBUTION:
                for _ in range(count):
                    company = random.choice(spec["companies"])
                    role = random.choice(spec["roles"])
                    prospect = Prospect(profile=_profile(company, role))
                    await repo.save_prospect(session, prospect)

                    persona = random.choice(personas) if personas else None
                    fit = round(random.uniform(72, 94), 1) if stage != FunnelStage.REJECTED else round(random.uniform(20, 45), 1)

                    link = CampaignProspectLink(
                        campaign_id=campaign.id, prospect_id=prospect.id, stage=stage,
                        fit_score=fit,
                        qualification_reasoning=(
                            f"{'Qualified' if stage != FunnelStage.REJECTED else 'Rejected'}: "
                            f"{'matches' if stage != FunnelStage.REJECTED else 'does not match'} target role & ICP; "
                            f"fit {fit}/100."
                        ),
                        persona_id=persona.id if persona else None,
                        human_approved=stage in (FunnelStage.CONTACTED, FunnelStage.ENGAGED, FunnelStage.MEETING, FunnelStage.OPPORTUNITY),
                        contact_count=random.randint(1, 3) if stage in (FunnelStage.CONTACTED, FunnelStage.ENGAGED, FunnelStage.MEETING, FunnelStage.OPPORTUNITY) else 0,
                        deal_value=round(random.uniform(3000, 8000), 0) if stage == FunnelStage.OPPORTUNITY else None,
                    )
                    await repo.save_link(session, link)

                    # --- AgentDecisions (research always; personalize/converse for advanced stages) ---
                    await repo.append_decision(session, AgentDecision(
                        campaign_id=campaign.id, prospect_id=prospect.id, agent_name=AgentName.RESEARCH,
                        verdict=DecisionVerdict.REJECT if stage == FunnelStage.REJECTED else DecisionVerdict.QUALIFY,
                        reasoning=link.qualification_reasoning or "Research decision.",
                        confidence=round(random.uniform(0.7, 0.95), 2),
                        details={"fit_score": fit, "persona_id": persona.id if persona else None},
                        model_used="template", latency_ms=random.randint(200, 900),
                        created_at=_now_minus(random.randint(120, 4000)),
                    ))

                    if stage in (FunnelStage.CONTACTED, FunnelStage.ENGAGED, FunnelStage.MEETING, FunnelStage.OPPORTUNITY):
                        chan = random.choice(enabled_channels)
                        # personalize decision + several outbound touches (drives spend/CAC).
                        await repo.append_decision(session, AgentDecision(
                            campaign_id=campaign.id, prospect_id=prospect.id, agent_name=AgentName.PERSONALIZE,
                            verdict=DecisionVerdict.SEND, reasoning=f"Drafted {chan.value} outreach (template).",
                            details={"channel": chan.value, "draft_method": "template"},
                            model_used="template", latency_ms=random.randint(300, 1200),
                            created_at=_now_minus(random.randint(60, 3000)),
                        ))
                        # Many touches per prospect (initial + a long follow-up
                        # cadence across channels), so Spend/CAC reach realistic
                        # dollar figures and LTV:CAC lands in a believable band.
                        n_touches = random.randint(30, 60)
                        for _ti in range(n_touches):
                            touch_seq += 1
                            tchan = random.choice(enabled_channels)
                            await repo.append_turn(session, ConversationTurn(
                                campaign_id=campaign.id, prospect_id=prospect.id, channel=tchan,
                                direction=Direction.OUTBOUND, content="Hi — quick note about what we're building…",
                                agent_name="personalize", created_at=_now_minus(random.randint(60, 3000)),
                            ))
                        # some also have an inbound reply (engaged+)
                        if stage in (FunnelStage.ENGAGED, FunnelStage.MEETING, FunnelStage.OPPORTUNITY):
                            await repo.append_turn(session, ConversationTurn(
                                campaign_id=campaign.id, prospect_id=prospect.id, channel=chan,
                                direction=Direction.INBOUND, content="Interesting — tell me more.",
                                created_at=_now_minus(random.randint(30, 2000)),
                            ))
                            await repo.append_decision(session, AgentDecision(
                                campaign_id=campaign.id, prospect_id=prospect.id, agent_name=AgentName.CONVERSE,
                                verdict=DecisionVerdict.CONTINUE, reasoning="Positive reply — continue the conversation.",
                                details={"category": "positive", "next_action": "reply"},
                                model_used="template", latency_ms=random.randint(200, 800),
                                created_at=_now_minus(random.randint(20, 1800)),
                            ))

            # A few escalations per campaign so the Escalations queue is populated.
            esc_prospects = (await repo.list_prospects_for_campaign(session, campaign.id))[:3]
            for link, prospect in esc_prospects:
                await repo.append_decision(session, AgentDecision(
                    campaign_id=campaign.id, prospect_id=prospect.id, agent_name=AgentName.CONVERSE,
                    verdict=DecisionVerdict.ESCALATE,
                    reasoning="Sensitive content (pricing / contract terms) — routed to a human.",
                    details={"category": "objection", "next_action": "human", "escalation_reason": "pricing & contract terms"},
                    model_used="template", latency_ms=random.randint(200, 700),
                    created_at=_now_minus(random.randint(10, 1500)),
                ))

            print(f"seeded: {campaign.name}  [{spec['status'].value}]  ({sum(c for _, c in _STAGE_DISTRIBUTION)} prospects)")

        await session.commit()
        print("\nDone. Log in as ava@sdrhq.io (manager) or mark@sdrhq.io (rep) to see full dashboards.")


async def _wipe() -> None:
    """Delete ONLY demo data (campaigns whose name starts with the DEMO prefix,
    plus their prospects/links/decisions/turns)."""
    async with SessionLocal() as session:
        camp_rows = (await session.execute(
            select(t.CampaignORM.id).where(t.CampaignORM.name.like(DEMO_PREFIX + "%"))
        )).scalars().all()
        if not camp_rows:
            print("No demo campaigns found to wipe.")
            return
        camp_ids = list(camp_rows)

        # Collect prospect ids belonging to these campaigns (via links) so we can
        # remove the prospect rows too (prospects table isn't campaign-scoped).
        link_rows = (await session.execute(
            select(t.CampaignProspectLinkORM.prospect_id).where(t.CampaignProspectLinkORM.campaign_id.in_(camp_ids))
        )).scalars().all()
        prospect_ids = list(set(link_rows))

        await session.execute(delete(t.AgentDecisionORM).where(t.AgentDecisionORM.campaign_id.in_(camp_ids)))
        await session.execute(delete(t.ConversationTurnORM).where(t.ConversationTurnORM.campaign_id.in_(camp_ids)))
        await session.execute(delete(t.CampaignProspectLinkORM).where(t.CampaignProspectLinkORM.campaign_id.in_(camp_ids)))
        await session.execute(delete(t.PersonaORM).where(t.PersonaORM.campaign_id.in_(camp_ids)))
        await session.execute(delete(t.CampaignAssetORM).where(t.CampaignAssetORM.campaign_id.in_(camp_ids)))
        if prospect_ids:
            await session.execute(delete(t.ProspectORM).where(t.ProspectORM.id.in_(prospect_ids)))
        await session.execute(delete(t.CampaignORM).where(t.CampaignORM.id.in_(camp_ids)))
        await session.commit()
        print(f"Wiped {len(camp_ids)} demo campaign(s) and {len(prospect_ids)} prospect(s).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed or wipe DEMO data.")
    ap.add_argument("--wipe", action="store_true", help="remove demo data instead of creating it")
    args = ap.parse_args()
    asyncio.run(_wipe() if args.wipe else _seed())


if __name__ == "__main__":
    main()