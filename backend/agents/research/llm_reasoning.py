"""Turns an already-made decision into a readable reasoning string.

The LLM here (when configured) NARRATES a decision that rules.py/scoring.py
already made — it cannot change the verdict or invent a qualification. This
is what keeps this agent hallucination-resistant: the one LLM call in the
loop has no power over the actual outcome.

TemplateReasoningGenerator needs no API key, no network call, and is the
default. GroqReasoningGenerator is an optional upgrade — Groq's free tier
(30 req/min, no credit card) is OpenAI-compatible, so this same client shape
works for Gemini's free tier too by swapping base_url/model.
"""
from __future__ import annotations

import os
from typing import Optional, Protocol

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ReasoningGenerator(Protocol):
    def generate(self, facts: dict) -> str: ...


class TemplateReasoningGenerator:
    """Zero-dependency default. Deterministic, free, instant."""

    def generate(self, facts: dict) -> str:
        verdict = facts["verdict"]
        fit_score = facts["fit_score"]
        matched = facts.get("matched", [])
        failed = facts.get("failed", [])
        persona_name = facts.get("persona_name")
        excluded = facts.get("excluded", False)
        exclusion_reason = facts.get("exclusion_reason")

        if excluded:
            return f"Rejected: matched exclusion criteria ({exclusion_reason})."

        parts = [f"{verdict.capitalize()}: fit score {fit_score}/100."]
        if matched:
            parts.append(f"Matched: {', '.join(matched)}.")
        if failed:
            parts.append(f"Did not match: {', '.join(failed)}.")
        if persona_name:
            parts.append(f"Assigned persona: {persona_name}.")
        return " ".join(parts)


class _OpenAICompatibleReasoningGenerator:
    """Base for any OpenAI-chat-compatible free tier (Groq, Gemini via its
    OpenAI-compat endpoint, etc). Never raises — callers should still wrap
    with FallbackReasoningGenerator, this is defense in depth."""

    def __init__(self, api_key: str, base_url: str, model: str, *, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, facts: dict) -> str:
        prompt = (
            "You are summarizing why a sales lead was scored the way it was. "
            "Write ONE short paragraph (max 3 sentences), no preamble, based ONLY on these facts "
            "(do not invent anything not listed here):\n"
            f"Verdict: {facts['verdict']}\n"
            f"Fit score: {facts['fit_score']}/100\n"
            f"Matched criteria: {facts.get('matched', [])}\n"
            f"Failed criteria: {facts.get('failed', [])}\n"
            f"Assigned persona: {facts.get('persona_name', 'none')}\n"
        )
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                }
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError):
            raise
        return payload["choices"][0]["message"]["content"].strip()


class GroqReasoningGenerator(_OpenAICompatibleReasoningGenerator):
    """Free tier: 30 req/min, no credit card. Check console.groq.com for the
    current recommended model id — passed explicitly rather than hardcoded
    since free-tier model availability changes over time."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile") -> None:
        super().__init__(
            api_key=api_key or os.getenv("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
            model=model,
        )


class GeminiReasoningGenerator(_OpenAICompatibleReasoningGenerator):
    """Free tier: 1,500 requests/day, no credit card, via Gemini's official
    OpenAI-compatible endpoint. Generally the more generous of the two free
    options, so default_reasoning_generator() prefers this when both keys
    are set. Get a key at https://aistudio.google.com/apikey"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash") -> None:
        super().__init__(
            api_key=api_key or os.getenv("GEMINI_API_KEY", ""),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model=model,
        )


class FallbackReasoningGenerator:
    """Tries `primary`; on ANY failure (no key, network error, rate limit,
    malformed response) falls back to `fallback` instead of crashing the
    agent. This is the reliability requirement from the PS engineering
    section applied specifically to the one network-dependent step here."""

    def __init__(self, primary: ReasoningGenerator, fallback: ReasoningGenerator) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(self, facts: dict) -> str:
        try:
            return self.primary.generate(facts)
        except Exception:
            return self.fallback.generate(facts)


def default_reasoning_generator() -> ReasoningGenerator:
    """Preference order: Gemini (more generous free tier) -> Groq -> pure
    template. Missing/invalid keys, network errors, or rate limits all
    silently degrade to the template rather than crashing the agent."""
    template = TemplateReasoningGenerator()
    if os.getenv("GEMINI_API_KEY"):
        return FallbackReasoningGenerator(primary=GeminiReasoningGenerator(), fallback=template)
    if os.getenv("GROQ_API_KEY"):
        return FallbackReasoningGenerator(primary=GroqReasoningGenerator(), fallback=template)
    return template