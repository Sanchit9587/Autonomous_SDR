"""Asset selection — RAG over campaign assets, reusing the same retriever the
Research agent uses. Retrieves the best-matching asset for the message context,
then filters by whether the chosen channel can actually carry it.
"""
from __future__ import annotations

from typing import Optional

from core.models import CampaignAsset, Channel
from rag.embeddings import get_default_vectorizer
from rag.retriever import KnowledgeRetriever

# Below this similarity, don't attach anything rather than force an irrelevant asset.
DEFAULT_MIN_ASSET_SIMILARITY = 0.05


def build_asset_retriever(assets: list[CampaignAsset]) -> KnowledgeRetriever:
    retriever = KnowledgeRetriever(vectorizer=get_default_vectorizer())
    for asset in assets:
        text = " ".join(filter(None, [asset.name, asset.description, " ".join(asset.tags)]))
        if text.strip():
            retriever.add_document(asset.id, text, metadata={"asset_id": asset.id})
    retriever.build()
    return retriever


def select_asset(
    query_text: str,
    assets: list[CampaignAsset],
    channel: Channel,
    *,
    min_similarity: float = DEFAULT_MIN_ASSET_SIMILARITY,
) -> Optional[str]:
    """Return the best-matching attachable asset id for this message context,
    or None if nothing is relevant enough or attachable on this channel."""
    attachable = [a for a in assets if a.is_attachable_on(channel.value)]
    if not attachable:
        return None

    retriever = build_asset_retriever(attachable)
    best = retriever.query_best(query_text)
    if best is None or best.score < min_similarity:
        return None
    return best.metadata.get("asset_id")