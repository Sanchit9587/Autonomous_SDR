"""Turns raw scraped page text into a short "what does this company do"
description, used as ProspectProfile.headline for company-centric prospects.

Same reliability shape as agents/research/llm_reasoning.py on purpose: a
zero-dependency template default, an optional Gemini/Groq upgrade (same
free-tier env vars the rest of the platform already uses — no separate key),
and a fallback wrapper that never lets a network hiccup break discovery.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CompanySummarizer(Protocol):
    def summarize(self, company_name: str, page_text: str) -> str: ...


class TemplateCompanySummarizer:
    """Zero-dependency default: takes the first real sentence out of the
    scraped text. Crude, but never empty and never wrong (it's a quote of
    the site's own words, not an invention)."""

    def summarize(self, company_name: str, page_text: str) -> str:
        if not page_text:
            return f"{company_name}: no page text available."
        # First sentence-ish chunk, capped so a run-on paragraph doesn't
        # dominate the RAG text blob.
        sentences = re.split(r"(?<=[.!?])\s+", page_text.strip())
        chunk = next((s for s in sentences if len(s) > 20), page_text[:200])
        return chunk[:280].strip()


class _OpenAICompatibleCompanySummarizer:
    """Base for any OpenAI-chat-compatible free tier (same shape as
    llm_reasoning.py's equivalent). Raises on failure — callers wrap with
    FallbackCompanySummarizer, this is defense in depth only."""

    def __init__(self, api_key: str, base_url: str, model: str, *, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def summarize(self, company_name: str, page_text: str) -> str:
        excerpt = page_text[:4000]
        prompt = (
            f"Based ONLY on the text below from {company_name}'s website, write ONE "
            "concise sentence (max 30 words) describing what the company does, for a "
            "sales lead brief. Do not invent details not present in the text.\n\n"
            f"{excerpt}"
        )
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 80,
                    "temperature": 0.2,
                }
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"].strip()


class GroqCompanySummarizer(_OpenAICompatibleCompanySummarizer):
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile") -> None:
        super().__init__(
            api_key=api_key or os.getenv("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
            model=model,
        )


class GeminiCompanySummarizer(_OpenAICompatibleCompanySummarizer):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash") -> None:
        super().__init__(
            api_key=api_key or os.getenv("GEMINI_API_KEY", ""),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model=model,
        )


class FallbackCompanySummarizer:
    def __init__(self, primary: CompanySummarizer, fallback: CompanySummarizer) -> None:
        self.primary = primary
        self.fallback = fallback

    def summarize(self, company_name: str, page_text: str) -> str:
        try:
            result = self.primary.summarize(company_name, page_text)
            return result or self.fallback.summarize(company_name, page_text)
        except (HTTPError, URLError, TimeoutError, KeyError, ValueError, Exception):
            return self.fallback.summarize(company_name, page_text)


def default_company_summarizer() -> CompanySummarizer:
    """Same key-preference order as default_reasoning_generator(): Gemini,
    then Groq, then the free template. Reuses whichever key the platform
    already has configured — discovery needs no LLM key of its own."""
    template = TemplateCompanySummarizer()
    if os.getenv("GEMINI_API_KEY"):
        return FallbackCompanySummarizer(primary=GeminiCompanySummarizer(), fallback=template)
    if os.getenv("GROQ_API_KEY"):
        return FallbackCompanySummarizer(primary=GroqCompanySummarizer(), fallback=template)
    return template