"""Combines the deterministic rule score with a RAG-retrieved semantic score,
and classifies persona the same way — by retrieving the best-matching
persona document, not by an LLM guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.models import Campaign, DecisionVerdict, Persona, ProspectProfile
from rag.embeddings import get_default_vectorizer
from rag.retriever import KnowledgeRetriever

DEFAULT_QUALIFY_THRESHOLD = 70.0
DEFAULT_REJECT_THRESHOLD = 40.0
DEFAULT_MIN_PERSONA_SIMILARITY = 0.05  # TF-IDF cosine sims run low in absolute terms; tune per corpus size


@dataclass
class ScoringResult:
    fit_score: float
    verdict: DecisionVerdict
    semantic_score: float
    persona_id: Optional[str]
    persona_similarity: Optional[float]


def build_campaign_retriever(campaign: Campaign, personas: list[Persona]) -> KnowledgeRetriever:
    """One retriever per campaign: indexes the ICP description as a whole,
    plus each persona's qualification notes, as separate retrievable docs."""
    retriever = KnowledgeRetriever(vectorizer=get_default_vectorizer())

    icp_text = " ".join(
        filter(None, [
            campaign.icp.keywords,
            " ".join(campaign.icp.target_roles),
            " ".join(campaign.icp.geography),
            campaign.icp.company_criteria,
        ])
    )
    if icp_text.strip():
        retriever.add_document("icp", icp_text, metadata={"type": "icp"})

    for persona in personas:
        persona_text = " ".join(filter(None, [persona.name, persona.description, persona.qualification_notes]))
        if persona_text.strip():
            retriever.add_document(persona.id, persona_text, metadata={"type": "persona", "persona_id": persona.id})

    retriever.build()
    return retriever


def _prospect_text(profile: ProspectProfile) -> str:
    return " ".join(filter(None, [profile.headline, profile.position, profile.company_name]))


def score_prospect(
    profile: ProspectProfile,
    rule_score: float,
    retriever: KnowledgeRetriever,
    *,
    qualify_threshold: float = DEFAULT_QUALIFY_THRESHOLD,
    reject_threshold: float = DEFAULT_REJECT_THRESHOLD,
    rule_weight: float = 0.5,
    min_persona_similarity: float = DEFAULT_MIN_PERSONA_SIMILARITY,
) -> ScoringResult:
    query_text = _prospect_text(profile)

    icp_match = retriever.query_best(query_text, metadata_filter={"type": "icp"})
    semantic_score = (icp_match.score if icp_match else 0.0) * 100.0

    persona_match = retriever.query_best(query_text, metadata_filter={"type": "persona"})
    persona_id: Optional[str] = None
    persona_similarity: Optional[float] = None
    if persona_match:
        persona_similarity = persona_match.score
        # Only assign a persona if the match is meaningfully similar — otherwise
        # a totally unrelated prospect would get forced into whichever persona
        # happened to score highest, however weak that match is.
        if persona_similarity >= min_persona_similarity:
            persona_id = persona_match.metadata.get("persona_id")

    fit_score = rule_weight * rule_score + (1 - rule_weight) * semantic_score

    if fit_score >= qualify_threshold:
        verdict = DecisionVerdict.QUALIFY
    elif fit_score < reject_threshold:
        verdict = DecisionVerdict.REJECT
    else:
        verdict = DecisionVerdict.NEEDS_REVIEW

    return ScoringResult(
        fit_score=round(fit_score, 1),
        verdict=verdict,
        semantic_score=round(semantic_score, 1),
        persona_id=persona_id,
        persona_similarity=round(persona_similarity, 3) if persona_similarity is not None else None,
    )