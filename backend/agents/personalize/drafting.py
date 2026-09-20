"""Message drafting, in priority order:
  1. Persona template for the channel  -> deterministic fill (safest, default).
  2. No template + LLM available       -> free-generation, grounded on the
     persona's example_messages via RAG + explicit tone.
  3. No template + no LLM              -> generic last-resort template baked in
     here, so the agent NEVER returns an empty draft.

The LLM path here (unlike Research's) produces customer-facing copy, so it is
grounded hard: retrieved examples + persona tone + low temperature.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from agents.personalize.templating import build_fill_context, fill_template
from core.models import Channel, MessageTemplate, Persona, Prospect, ToneEnum
from rag.embeddings import get_default_vectorizer
from rag.retriever import KnowledgeRetriever

# Baked-in, per-channel last resort so a missing template + missing LLM never
# yields an empty message. Deliberately generic and safe.
_GENERIC_TEMPLATES: dict[str, str] = {
    Channel.EMAIL.value: "Hi {{first_name}}, I came across your work at {{company}} and would love to connect.",
    Channel.LINKEDIN.value: "Hi {{first_name}}, noticed your work at {{company}} — would love to connect.",
    Channel.SMS.value: "Hi {{first_name}}, reaching out about {{company}} — open to a quick chat?",
    Channel.VOICE.value: "Hi {{first_name}}, calling regarding your work at {{company}}.",
}


@dataclass
class DraftResult:
    subject: Optional[str]
    body: str
    method: str                 # 'template' | 'llm' | 'generic_fallback'


class MessageDrafter(Protocol):
    def draft(self, *, prospect: Prospect, persona: Optional[Persona], channel: Channel,
              context_type: str, research_reasoning: Optional[str],
              goals: Optional[list[str]] = None) -> DraftResult: ...


def _example_grounding(persona: Optional[Persona], channel: Channel, query_text: str, k: int = 2) -> list[str]:
    """Retrieve the most relevant example messages for few-shot grounding."""
    if not persona:
        return []
    examples = persona.example_messages.get(channel.value, [])
    if not examples:
        return []
    retriever = KnowledgeRetriever(vectorizer=get_default_vectorizer())
    for i, ex in enumerate(examples):
        retriever.add_document(f"ex_{i}", ex, metadata={"text": ex})
    retriever.build()
    hits = retriever.query(query_text, k=k)
    return [h.text for h in hits] or examples[:k]


class TemplateOrGenericDrafter:
    """Zero-LLM drafter: uses the persona template if present, else the baked-in
    generic template. Always works, no keys, no network."""

    def draft(self, *, prospect, persona, channel, context_type, research_reasoning, goals=None) -> DraftResult:
        fill_ctx = build_fill_context(prospect)
        template: Optional[MessageTemplate] = persona.template_for(channel) if persona else None
        if template is not None:
            subject = fill_template(template.subject_template, fill_ctx) if template.subject_template else None
            return DraftResult(subject=subject, body=fill_template(template.body_template, fill_ctx), method="template")
        generic = _GENERIC_TEMPLATES.get(channel.value, _GENERIC_TEMPLATES[Channel.EMAIL.value])
        return DraftResult(subject=None, body=fill_template(generic, fill_ctx), method="generic_fallback")


class LLMDrafter:
    """Free-generation via an OpenAI-compatible free tier (Gemini/Groq). Falls
    back to `fallback` on template-present, no-key, or any error."""

    def __init__(self, api_key: str, base_url: str, model: str, fallback: MessageDrafter, *, timeout: float = 20.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback = fallback
        self.timeout = timeout

    def draft(self, *, prospect, persona, channel, context_type, research_reasoning, goals=None) -> DraftResult:
        # If a template exists, prefer the deterministic path — no LLM needed.
        if persona and persona.template_for(channel) is not None:
            return self.fallback.draft(prospect=prospect, persona=persona, channel=channel,
                                       context_type=context_type, research_reasoning=research_reasoning, goals=goals)
        try:
            return self._generate(prospect, persona, channel, context_type, research_reasoning, goals)
        except Exception:
            return self.fallback.draft(prospect=prospect, persona=persona, channel=channel,
                                       context_type=context_type, research_reasoning=research_reasoning, goals=goals)

    def _generate(self, prospect, persona, channel, context_type, research_reasoning, goals=None) -> DraftResult:
        p = prospect.profile
        tone = (persona.tone.value if persona else ToneEnum.PROFESSIONAL.value)
        tone_notes = (persona.tone_notes if persona and persona.tone_notes else "")
        query_text = " ".join(filter(None, [p.headline, p.position, p.company_name, research_reasoning]))
        examples = _example_grounding(persona, channel, query_text)
        examples_block = "\n".join(f"- {ex}" for ex in examples) if examples else "(none provided)"

        is_follow_up = context_type.startswith("follow_up")
        goal_line = ""
        if goals:
            goal_line = (
                f"Campaign goal(s): {', '.join(goals)}. Make the call-to-action drive toward "
                f"the primary goal (e.g. book_meeting -> propose a call; signup/free_trial -> "
                f"invite to sign up; sale -> move toward purchase).\n"
            )
        prompt = (
            f"Write a {channel.value} outreach message to a sales prospect.\n"
            f"This is a {'follow-up' if is_follow_up else 'first-touch cold'} message.\n"
            f"Tone: {tone}. {tone_notes}\n"
            f"{goal_line}"
            f"Prospect: {p.name}, {p.position or ''} at {p.company_name or ''}. Headline: {p.headline or ''}.\n"
            f"Why they fit (from research): {research_reasoning or 'n/a'}\n"
            f"Reference examples of messages that worked for this persona:\n{examples_block}\n\n"
            "Rules: personalize using the prospect's actual details, keep it concise "
            f"({'2-3 sentences' if channel.value != 'email' else 'under 120 words'}), "
            "no placeholders, no subject line in the body. Output only the message text."
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.4},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()["choices"][0]["message"]["content"].strip()
        subject = None
        if channel == Channel.EMAIL:
            subject = f"Quick note for {p.name.split()[0]}" if p.name else "Quick note"
        return DraftResult(subject=subject, body=body, method="llm")


def default_drafter() -> MessageDrafter:
    """Gemini -> Groq -> template/generic, same preference order as Research."""
    fallback = TemplateOrGenericDrafter()
    if os.getenv("GEMINI_API_KEY"):
        return LLMDrafter(os.getenv("GEMINI_API_KEY", ""), "https://generativelanguage.googleapis.com/v1beta/openai",
                          "gemini-2.5-flash", fallback=fallback)
    if os.getenv("GROQ_API_KEY"):
        return LLMDrafter(os.getenv("GROQ_API_KEY", ""), "https://api.groq.com/openai/v1",
                          "llama-3.3-70b-versatile", fallback=fallback)
    return fallback