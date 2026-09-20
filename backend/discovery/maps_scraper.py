"""Google Maps business discovery (Playwright).

Finds businesses matching a search query and pulls name/phone/website/address
straight off the Maps listing panel. This is the "who are the candidate
businesses" stage; contact enrichment (email, about-text) happens separately
in company_research.py once we have each business's website domain.

Local-only: needs a real Chromium binary (`playwright install chromium`), and
can take tens of seconds per query. Not usable on Vercel serverless — see the
IS_VERCEL guard around the /discover endpoint in orchestrator/api.py.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright


@dataclass
class MapsListing:
    name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None


async def _scrape_one_listing(page, prev_name: Optional[str]) -> MapsListing:
    # Wait for the detail pane's heading to actually populate with a NEW
    # business's name before reading it — a fixed sleep is a race: the
    # previous listing's pane can still be showing when we start reading.
    try:
        await page.wait_for_function(
            """(prevName) => {
                const hs = [...document.querySelectorAll('h1')];
                const match = hs.find(h => h.innerText.trim() && h.innerText.trim() !== 'Results');
                return !!match && match.innerText.trim() !== prevName;
            }""",
            arg=prev_name,
            timeout=10000,
        )
    except Exception:
        pass

    name = "Unknown"
    for h in await page.query_selector_all("h1"):
        text = (await h.inner_text()).strip()
        if text and text != "Results":
            name = text

    phone = None
    phone_btn = page.locator('button[aria-label^="Phone:"]').first
    if await phone_btn.count():
        label = await phone_btn.get_attribute("aria-label")
        phone = label.split("Phone:", 1)[1].strip()

    website = None
    website_link = page.locator('a[aria-label^="Website:"]').first
    if await website_link.count():
        website = await website_link.get_attribute("href")

    address = None
    address_btn = page.locator('button[aria-label^="Address:"]').first
    if await address_btn.count():
        label = await address_btn.get_attribute("aria-label")
        address = label.split("Address:", 1)[1].strip()

    return MapsListing(name=name, phone=phone, website=website, address=address)


async def scrape_google_maps(search_query: str, max_results: int = 10) -> list[MapsListing]:
    """Scrapes Google Maps for businesses matching search_query."""
    results: list[MapsListing] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        query_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        await page.goto(query_url, wait_until="domcontentloaded", timeout=30000)

        feed_selector = 'div[role="feed"]'
        try:
            await page.wait_for_selector(feed_selector, timeout=10000)
        except Exception:
            await browser.close()
            return results  # no results feed at all (e.g. a single exact-match business)

        items_selector = f"{feed_selector} > div > div > a"
        while True:
            elements = await page.query_selector_all(items_selector)
            if len(elements) >= max_results:
                break
            prev_count = len(elements)
            await page.eval_on_selector(feed_selector, "el => el.scrollBy(0, 1000)")
            await asyncio.sleep(1.5)
            new_count = len(await page.query_selector_all(items_selector))
            if new_count == prev_count:
                break  # scrolling loaded nothing new — fewer results than requested

        listings = await page.query_selector_all(items_selector)
        prev_name: Optional[str] = None

        for idx in range(min(len(listings), max_results)):
            try:
                current_listings = await page.query_selector_all(items_selector)
                await current_listings[idx].click()
                listing = await _scrape_one_listing(page, prev_name)
                prev_name = listing.name
                results.append(listing)
            except Exception:
                continue  # one bad listing shouldn't abort the whole scrape

        await browser.close()

    return results