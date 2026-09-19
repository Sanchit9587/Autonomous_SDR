"""A small, per-campaign knowledge retriever.

This IS the RAG piece the PS asks for, scoped small on purpose: each campaign's
knowledge base (ICP description, persona notes, playbook snippets, example
messages) is tiny — a handful to a few dozen documents — so an in-memory
vectorizer is the right amount of infrastructure today. Swapping the backing
store for pgvector/Qdrant later means changing this file only; every agent
calls the same `query()` interface regardless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from rag.embeddings import TextVectorizer, TfidfVectorizerBackend


@dataclass
class RetrievedDocument:
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeRetriever:
    def __init__(self, vectorizer: Optional[TextVectorizer] = None) -> None:
        self._vectorizer: TextVectorizer = vectorizer or TfidfVectorizerBackend()
        self._doc_ids: list[str] = []
        self._texts: list[str] = []
        self._metadata: list[dict[str, Any]] = []
        self._matrix: Optional[np.ndarray] = None

    def add_document(self, doc_id: str, text: str, metadata: Optional[dict[str, Any]] = None) -> None:
        self._doc_ids.append(doc_id)
        self._texts.append(text)
        self._metadata.append(metadata or {})

    def build(self) -> None:
        """Must be called once after all add_document() calls, before query()."""
        if not self._texts:
            self._matrix = None
            return
        self._vectorizer.fit(self._texts)
        self._matrix = self._vectorizer.transform(self._texts)

    def query(self, text: str, k: int = 3) -> list[RetrievedDocument]:
        """Top-k most similar documents to `text`. Never raises — an empty or
        unbuilt retriever just returns no results, so a missing knowledge base
        degrades gracefully instead of crashing the calling agent."""
        if self._matrix is None or self._matrix.shape[0] == 0:
            return []

        query_vec = self._vectorizer.transform([text])
        if query_vec.shape[1] != self._matrix.shape[1]:
            return []  # vectorizer wasn't fitted on this query's vocabulary space

        scores = _cosine_similarity(query_vec, self._matrix)[0]
        ranked_idx = np.argsort(-scores)[:k]
        return [
            RetrievedDocument(doc_id=self._doc_ids[i], text=self._texts[i], score=float(scores[i]), metadata=self._metadata[i])
            for i in ranked_idx
        ]

    def query_best(self, text: str, metadata_filter: Optional[dict[str, Any]] = None) -> Optional[RetrievedDocument]:
        """Convenience: best match, optionally restricted to docs whose metadata
        matches every key/value in metadata_filter (e.g. {"type": "persona"})."""
        results = self.query(text, k=max(len(self._doc_ids), 1))
        if metadata_filter:
            results = [r for r in results if all(r.metadata.get(k) == v for k, v in metadata_filter.items())]
        return results[0] if results else None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a_norm @ b_norm.T