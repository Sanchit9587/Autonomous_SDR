"""Deterministic ICP criteria matching. Not ML on purpose: role/geography/
exclusion checks are exact-ish string matches, and a rule is faster, free,
and more auditable here than an LLM call would be.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.models import ICPFilter, ProspectProfile


@dataclass
class RuleResult:
    score: float                       # 0-100, based only on criteria that were actually specified
    matched: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    excluded: bool = False             # hard-fail: matched an exclusion criterion
    exclusion_reason: str | None = None


def _contains_any(haystack: str | None, needles: list[str]) -> bool:
    if not haystack or not needles:
        return False
    haystack_lower = haystack.lower()
    return any(needle.lower() in haystack_lower for needle in needles if needle)


def evaluate_icp_rules(profile: ProspectProfile, icp: ICPFilter) -> RuleResult:
    matched: list[str] = []
    failed: list[str] = []
    evaluated = 0

    if icp.target_roles:
        evaluated += 1
        if _contains_any(profile.position, icp.target_roles) or _contains_any(profile.headline, icp.target_roles):
            matched.append("role")
        else:
            failed.append("role")

    if icp.geography:
        evaluated += 1
        if _contains_any(profile.location, icp.geography):
            matched.append("geography")
        else:
            failed.append("geography")

    if icp.keywords:
        evaluated += 1
        keyword_list = [icp.keywords]
        if _contains_any(profile.headline, keyword_list) or _contains_any(profile.company_name, keyword_list):
            matched.append("keywords")
        else:
            failed.append("keywords")

    # Exclusion is a hard stop, independent of the score below.
    if icp.exclusion_criteria:
        exclusion_terms = [t.strip() for t in icp.exclusion_criteria.split(",") if t.strip()]
        if _contains_any(profile.position, exclusion_terms) or _contains_any(profile.company_name, exclusion_terms):
            return RuleResult(score=0.0, matched=matched, failed=failed, excluded=True, exclusion_reason=icp.exclusion_criteria)

    score = (len(matched) / evaluated * 100.0) if evaluated > 0 else 50.0  # neutral score if ICP under-specified
    return RuleResult(score=score, matched=matched, failed=failed)