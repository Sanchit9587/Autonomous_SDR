"""Per-company web enrichment: given a business's website domain, finds more
contact info (emails/phones) and enough page text to describe what the
company does, for ProspectProfile.headline.

Two sources, combined:
  1. The homepage itself (always fetched, no search needed).
  2. A couple of targeted Google searches ("dorks") via the Serper.dev API,
     scoped to the domain and the campaign's ICP keywords, whose results are
     also fetched and mined.

SERPER_API_KEY must be set in the environment — there is no hardcoded
fallback key (the experimental version this was adapted from leaked live
keys into source; don't repeat that). If it's unset, dork search is skipped
and discovery falls back to homepage-only enrichment.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from core.models import ICPFilter
from discovery.summarizer import CompanySummarizer, default_company_summarizer

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
PHONE_REGEX = r"\(?\b[2-9]\d{2}\)?[-. ]?\d{3}[-. ]?\d{4}\b"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# Placeholder/boilerplate domains that show up in privacy-policy templates,
# tracking pixels, and CMS assets rather than real business contact emails.
JUNK_EMAIL_DOMAINS = {
    "example.com", "domain.com", "yourdomain.com", "email.com",
    "sentry.io", "wixpress.com", "godaddy.com", "schema.org", "w3.org",
    "yoursite.com", "test.com",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class CompanyEnrichment:
    emails: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    about_text: str = ""  # goes into ProspectProfile.headline


def is_configured() -> bool:
    """Whether dork search is available. Homepage-only enrichment still
    works without this — see enrich_company()."""
    return bool(SERPER_API_KEY)


def _clean_emails(raw_emails: list[str]) -> set[str]:
    cleaned = set()
    for email in raw_emails:
        email = email.lower()
        if email.endswith(IMAGE_EXTENSIONS):
            continue
        domain = email.split("@", 1)[1]
        if domain in JUNK_EMAIL_DOMAINS:
            continue
        cleaned.add(email)
    return cleaned


def _generate_dorks(domain: str, company_name: str, icp: ICPFilter) -> list[str]:
    """Two targeted searches, scoped by the campaign's own ICP rather than
    hardcoded terms: one for contact info, one for "what do you do" content
    that feeds the headline summary."""
    dorks = [f'site:{domain} "contact" OR "email" OR "@{domain}"']
    about_terms = '"about us" OR "who we are" OR "our company"'
    if icp.keywords:
        about_terms += f' "{icp.keywords}"'
    dorks.append(f"site:{domain} {about_terms}")
    return dorks


def _search_dork(query: str, num_results: int = 5) -> list[str]:
    """Returns result links, or [] on any failure (never raises)."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = httpx.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    return [r["link"] for r in data.get("organic", []) if r.get("link")]


def _fetch_page(url: str, timeout: float = 15.0) -> tuple[str, BeautifulSoup] | tuple[None, None]:
    try:
        resp = httpx.get(url, headers=REQUEST_HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    return text, soup


def enrich_company(
    domain: str,
    company_name: str,
    icp: ICPFilter,
    max_pages: int = 4,
    summarizer: CompanySummarizer | None = None,
) -> CompanyEnrichment:
    """Fetches the homepage plus up to max_pages dork results for `domain`,
    and returns merged emails/phones/about-text. Never raises — a fully
    unreachable domain just yields an empty result."""
    summarizer = summarizer or default_company_summarizer()
    result = CompanyEnrichment()
    visited: set[str] = set()
    all_text: list[str] = []

    homepage = domain if domain.startswith("http") else f"https://{domain}"
    urls = [homepage]
    if is_configured():
        for dork in _generate_dorks(domain, company_name, icp):
            urls.extend(_search_dork(dork))

    for url in urls:
        if len(visited) >= max_pages or url in visited:
            continue
        visited.add(url)
        text, _soup = _fetch_page(url)
        if not text:
            continue
        result.emails |= _clean_emails(re.findall(EMAIL_REGEX, text))
        result.phones |= set(re.findall(PHONE_REGEX, text))
        all_text.append(text)

    if all_text:
        # Longest page is usually the homepage or an "about" page, not a
        # thin contact-only page — best material for the summary.
        best_text = max(all_text, key=len)
        result.about_text = summarizer.summarize(company_name, best_text)

    return result