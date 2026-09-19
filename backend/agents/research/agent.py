"""The Research agent.

Pipeline, cheapest-first:
  1. Enrichment (Apollo connector) — plain API call, no ML.
  2. Deterministic ICP rule matching — plain Python, no ML.
  3. RAG-based semantic scoring + persona classification — free-tier
     scikit-learn TF-IDF retrieval, no LLM, no GPU.
  4. Reasoning narration — the ONE optional LLM call, narrating (not
     deciding) the outcome; defaults to a free template with no network
     call at all.

Returns an AgentDecision only. Per the base Agent contract, this agent never
calls state_machine.transition() or mutates the campaign/link itself — the
orchestrator does that based on the returned verdict.
"""
from __future__ import annotations

from typing import Optional

from agents.base import Agent, AgentContext
from agents.research.llm_reasoning import ReasoningGenerator, default_reasoning_generator
from agents.research.rules import evaluate_icp_rules
from agents.research.scoring import build_campaign_retriever, score_prospect
from core.models import AgentDecision, AgentName, DecisionVerdict, Persona


class ResearchAgent(Agent):
    def __init__(
        self,
        *,
        apollo_client=None,                              # optional: scrapers.apollo_client.ApolloEnrichmentClient
        reasoning_generator: Optional[ReasoningGenerator] = None,
    ) -> None:
        self.apollo_client = apollo_client
        self.reasoning_generator = reasoning_generator or default_reasoning_generator()

    def run(self, context: AgentContext) -> AgentDecision:
        profile = context.prospect.profile

        # Step 1: enrichment (optional — agent works fine with no Apollo key configured)
        enrichment_note = "skipped (no enrichment client configured)"
        if self.apollo_client is not None:
            try:
                result = self.apollo_client.enrich_profile(
                    linkedin_url=profile.linkedin_url or "",
                    name=profile.name,
                    company=profile.company_name or "",
                )
                if result.get("work_email"):
                    profile.work_email = result["work_email"]
                profile.enrichment_status = result.get("status", "error")
                enrichment_note = profile.enrichment_status
            except Exception as exc:  # never let enrichment failure crash qualification
                profile.enrichment_status = "error"
                enrichment_note = f"error: {exc}"

        # Step 2: deterministic ICP rules
        rule_result = evaluate_icp_rules(profile, context.campaign.icp)

        if rule_result.excluded:
            reasoning = self.reasoning_generator.generate({
                "verdict": DecisionVerdict.REJECT.value, "fit_score": 0,
                "matched": rule_result.matched, "failed": rule_result.failed,
                "excluded": True, "exclusion_reason": rule_result.exclusion_reason,
            })
            return AgentDecision(
                campaign_id=context.campaign.id, prospect_id=context.prospect.id,
                agent_name=AgentName.RESEARCH, prompt_version_id=context.prompt_version_id,
                verdict=DecisionVerdict.REJECT, reasoning=reasoning,
                details={"fit_score": 0, "excluded": True, "exclusion_reason": rule_result.exclusion_reason, "enrichment": enrichment_note},
            )

        # Step 3: RAG-based semantic score + persona classification
        retriever = build_campaign_retriever(context.campaign, context.personas)
        research_settings = context.campaign.agent_settings.get(AgentName.RESEARCH.value)
        qualify_threshold = (research_settings.decision_threshold if research_settings and research_settings.decision_threshold else 70.0)

        scoring = score_prospect(profile, rule_result.score, retriever, qualify_threshold=qualify_threshold)

        persona_name = None
        if scoring.persona_id:
            persona_name = next((p.name for p in context.personas if p.id == scoring.persona_id), None)

        # Step 4: reasoning narration (template by default, optional LLM upgrade)
        reasoning = self.reasoning_generator.generate({
            "verdict": scoring.verdict.value, "fit_score": scoring.fit_score,
            "matched": rule_result.matched, "failed": rule_result.failed,
            "persona_name": persona_name,
        })

        return AgentDecision(
            campaign_id=context.campaign.id, prospect_id=context.prospect.id,
            agent_name=AgentName.RESEARCH, prompt_version_id=context.prompt_version_id,
            verdict=scoring.verdict, reasoning=reasoning,
            details={
                "fit_score": scoring.fit_score,
                "semantic_score": scoring.semantic_score,
                "matched_criteria": rule_result.matched,
                "failed_criteria": rule_result.failed,
                "persona_id": scoring.persona_id,
                "persona_similarity": scoring.persona_similarity,
                "enrichment": enrichment_note,
            },
        )