# Personalize Agent — Drafting Prompt (v1)

Used by `drafting.py`'s `LLMDrafter` only when no persona template exists for
the chosen channel. Produces customer-facing copy, so it is grounded on:
persona tone + tone_notes, the prospect's real details, the Research agent's
fit reasoning, and RAG-retrieved example_messages for the persona/channel.

## Intent
Concise, personalized, no placeholders, no invented facts. First-touch vs
follow-up framing controlled by context_type. Low temperature (0.4).

## Change log
- v1 (initial): grounded free-generation with few-shot examples + tone.