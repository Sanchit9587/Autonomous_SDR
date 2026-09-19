"""Deterministic template filling. Placeholders like {{first_name}} are filled
from prospect facts; no LLM needed for the template path (the safe, low-
hallucination default whenever a persona has a template for the chosen channel).
"""
from __future__ import annotations

import re
from typing import Optional

from core.models import Prospect

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name else ""


def build_fill_context(prospect: Prospect) -> dict[str, str]:
    p = prospect.profile
    return {
        "first_name": _first_name(p.name),
        "name": p.name or "",
        "company": p.company_name or "",
        "position": p.position or "",
        "headline": p.headline or "",
        "location": p.location or "",
    }


def fill_template(template_text: str, context: dict[str, str]) -> str:
    """Replace {{key}} with context[key]. Unknown placeholders are left blank
    rather than crashing, and surrounding whitespace is tidied so a missing
    field doesn't leave awkward double spaces."""
    def _sub(match: re.Match) -> str:
        return context.get(match.group(1), "")

    filled = _PLACEHOLDER.sub(_sub, template_text)
    return re.sub(r"[ \t]{2,}", " ", filled).strip()