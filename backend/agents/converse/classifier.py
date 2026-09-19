"""Reply classification. LLM zero-shot by default (Gemini -> Groq), with a
keyword-rule fallback so it still works with no key. A trained scikit-learn
classifier is the intended v2 once labeled reply data exists — this module's
interface (classify() -> Classification) won't change when that swaps in.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

# Bounded category set — the policy table in policy.py maps each to an action.
CATEGORIES = ["positive", "meeting_request", "question", "objection", "negative", "unsubscribe", "out_of_office"]


@dataclass
class Classification:
    category: str
    sentiment: str          # "positive" | "neutral" | "negative"
    confidence: float       # 0-1
    method: str             # "llm" | "keyword_fallback"


class ReplyClassifier(Protocol):
    def classify(self, message: str) -> Classification: ...


class KeywordClassifier:
    """Zero-dependency fallback. Crude but keeps the agent working with no key."""

    def classify(self, message: str) -> Classification:
        m = message.lower()
        if any(w in m for w in ["unsubscribe", "stop emailing", "remove me", "opt out", "opt-out"]):
            return Classification("unsubscribe", "negative", 0.9, "keyword_fallback")
        if any(w in m for w in ["out of office", "on leave", "vacation", "away until"]):
            return Classification("out_of_office", "neutral", 0.8, "keyword_fallback")
        if any(w in m for w in ["not interested", "no thanks", "no thank you", "please don't", "not a fit"]):
            return Classification("negative", "negative", 0.7, "keyword_fallback")
        if any(w in m for w in ["book", "calendar", "schedule a call", "let's meet", "set up a", "demo"]):
            return Classification("meeting_request", "positive", 0.7, "keyword_fallback")
        if any(w in m for w in ["how much", "pricing", "price", "cost", "but ", "concern", "worried"]):
            return Classification("objection", "neutral", 0.55, "keyword_fallback")
        if "?" in message:
            return Classification("question", "neutral", 0.55, "keyword_fallback")
        if any(w in m for w in ["interested", "sounds good", "tell me more", "yes"]):
            return Classification("positive", "positive", 0.6, "keyword_fallback")
        return Classification("question", "neutral", 0.3, "keyword_fallback")  # low-confidence default -> escalation


class LLMClassifier:
    """Zero-shot classification via an OpenAI-compatible free tier. Falls back
    to `fallback` on no-key / error / unparseable output."""

    def __init__(self, api_key: str, base_url: str, model: str, fallback: ReplyClassifier, *, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback = fallback
        self.timeout = timeout

    def classify(self, message: str) -> Classification:
        try:
            return self._classify(message)
        except Exception:
            return self.fallback.classify(message)

    def _classify(self, message: str) -> Classification:
        prompt = (
            "Classify this sales-outreach reply. Respond with ONLY a JSON object, no prose.\n"
            f"Categories: {CATEGORIES}\n"
            'Format: {"category": "<one of the categories>", "sentiment": "positive|neutral|negative", "confidence": 0.0-1.0}\n\n'
            f"Reply:\n{message}"
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 100, "temperature": 0.0},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        category = data.get("category", "question")
        if category not in CATEGORIES:
            category = "question"
        return Classification(
            category=category,
            sentiment=data.get("sentiment", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
            method="llm",
        )


def default_classifier() -> ReplyClassifier:
    fallback = KeywordClassifier()
    if os.getenv("GEMINI_API_KEY"):
        return LLMClassifier(os.getenv("GEMINI_API_KEY", ""), "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", fallback=fallback)
    if os.getenv("GROQ_API_KEY"):
        return LLMClassifier(os.getenv("GROQ_API_KEY", ""), "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", fallback=fallback)
    return fallback