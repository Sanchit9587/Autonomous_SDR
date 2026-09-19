# Research Agent — Reasoning Prompt (v1)

Used only by `llm_reasoning.py`'s optional LLM-backed generators, to narrate
a decision that `rules.py` + `scoring.py` already made deterministically.
The LLM never decides the verdict — it only writes a short explanation of
facts it's given. See `_OpenAICompatibleReasoningGenerator.generate()` for
the exact prompt text sent (kept in code, not this file, since it's built
dynamically from the decision's facts — this file documents intent and
change history for version tracking).

## Intent
One short paragraph (max 3 sentences), grounded strictly in the provided
facts: verdict, fit score, matched/failed criteria, assigned persona.
No invented details, no speculation beyond the given facts.

## Change log
- v1 (initial): baseline factual-summary framing, 150 max_tokens, temperature 0.3.