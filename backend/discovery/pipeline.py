"""Discovery pipeline: ICP -> Maps search -> per-domain enrichment -> Prospects.

This is the "find new companies" stage that feeds a campaign's Prospects list
at the `discovered` funnel stage, same as a CSV import — the manager still
clicks "Research all discovered" afterwards to run the Research agent.

Local-only (see maps_scraper.py's docstring) — the /discover endpoint in
orchestrator/api.py refuses to run this on Vercel.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from core.models import ICPFilter, Prospect, ProspectProfile
from discovery import company_research
from discovery.maps_scraper import MapsListing, scrape_google_maps
from discovery.summarizer import default_company_summarizer


def build_search_query(icp: ICPFilter, campaign_name: str) -> str:
    """Turns a campaign's ICP into a Google Maps search query. Prefers the
    ICP's own free-text targeting fields; falls back to the campaign name so
    a bare-bones campaign still produces a usable (if generic) search."""
    what = icp.company_criteria or icp.keywords
    where = ", ".join(icp.geography) if icp.geography else None

    if what and where:
        return f"{what} in {where}"
    if what:
        return what
    if where:
        return f"companies in {where}"
    return campaign_name


def _get_domain(url: str | None) -> str | None:
    if not url:
        return None
    netloc = urlparse(url).netloc or urlparse(url).path
    netloc = netloc.lower().split(":")[0].split("/")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def discover_companies(
    icp: ICPFilter,
    campaign_name: str,
    max_results: int = 10,
    max_pages_per_domain: int = 4,
) -> list[Prospect]:
    """Runs the full pipeline and returns Prospect objects ready to save.
    A business with no website still comes back as a lead (name/phone only,
    no email/about-text) rather than being silently dropped."""
    query = build_search_query(icp, campaign_name)
    listings: list[MapsListing] = asyncio.run(scrape_google_maps(query, max_results=max_results))

    summarizer = default_company_summarizer()  # built once, shared across all enrichment calls
    prospects: list[Prospect] = []

    # Global dedup: once an email/phone is attached to one prospect, later
    # businesses don't repeat it (mirrors the CSV importer's per-campaign
    # dedupe, but here across the whole batch since these are all new).
    seen_emails: set[str] = set()
    seen_phones: set[str] = set()

    for listing in listings:
        domain = _get_domain(listing.website)
        emails: set[str] = set()
        phones: set[str] = set(filter(None, [listing.phone]))
        headline = None

        if domain:
            enrichment = company_research.enrich_company(
                domain, listing.name, icp, max_pages=max_pages_per_domain, summarizer=summarizer
            )
            emails |= enrichment.emails
            phones |= enrichment.phones
            headline = enrichment.about_text or None

        emails = {e for e in emails if e not in seen_emails}
        phones = {p for p in phones if p not in seen_phones}
        seen_emails |= emails
        seen_phones |= phones

        profile = ProspectProfile(
            name=listing.name,
            company_name=listing.name,
            website=listing.website,
            headline=headline,
            location=listing.address,
            work_email=sorted(emails)[0] if emails else None,
            phone_numbers=sorted(phones),
        )
        prospects.append(Prospect(profile=profile))

    return prospects