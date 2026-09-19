"""Pluggable text vectorization for the RAG retriever.

TfidfVectorizerBackend is the default: pure scikit-learn, no downloads, no
GPU, works instantly offline. SentenceTransformerBackend is an optional
upgrade for better semantic quality — it downloads a small (~90MB) CPU-only
model on first use. Swapping between them is a one-line change in whoever
constructs the retriever; nothing else in the codebase needs to know which
backend is active.
"""
from __future__ import annotations

import os
from typing import Protocol

import numpy as np


class TextVectorizer(Protocol):
    def fit(self, texts: list[str]) -> None: ...
    def transform(self, texts: list[str]) -> np.ndarray: ...


class TfidfVectorizerBackend:
    """Default backend: lexical similarity, weighted by term rarity.

    Catches exact/near-exact wording overlap (e.g. "VP Engineering" vs
    "VP of Engineering") well; misses pure synonyms (e.g. "Head of Platform"
    vs "VP Engineering") that a real embedding model would catch. Good
    enough to start with, and the point where sentence-transformers is worth
    upgrading to later.
    """

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer  # local import: keep sklearn optional at module load

        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        if not texts:
            self._fitted = False
            return
        self._vectorizer.fit(texts)
        self._fitted = True

    def transform(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            return np.zeros((len(texts), 1))
        return self._vectorizer.transform(texts).toarray()


class SentenceTransformerBackend:
    """Optional upgrade: real semantic embeddings, still CPU-only.

    Not imported until instantiated, so this whole file stays usable even if
    `sentence-transformers`/`torch` are never installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, deferred on purpose

        self._model = SentenceTransformer(model_name)

    def fit(self, texts: list[str]) -> None:
        pass  # pretrained model, nothing to fit

    def transform(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1))
        return np.asarray(self._model.encode(texts))


def get_default_vectorizer() -> TextVectorizer:
    """Reads RESEARCH_EMBEDDING_BACKEND ('tfidf' default, or 'sentence_transformers'
    for the higher-quality CPU upgrade). Every agent that builds a retriever
    should go through this rather than hardcoding a backend, so the whole
    system upgrades together with one env var."""
    backend = os.getenv("RESEARCH_EMBEDDING_BACKEND", "tfidf").lower()
    if backend == "sentence_transformers":
        return SentenceTransformerBackend()
    return TfidfVectorizerBackend()