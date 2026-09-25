"""Best-effort company website scrape, used to ground AI personalization in
real, current web content instead of only whatever's already in our DB.

Fetches the company's own homepage (never a third-party profile — LinkedIn
etc. block/ToS-prohibit scraping and would be unreliable anyway) and
extracts visible text. A failure here (no domain on file, site down,
timeout, non-HTML response) is a normal outcome, not an error: it simply
means personalization proceeds with only the DB-sourced facts it already
had, same never-fabricate convention as the rest of this codebase — no
scraped content ever gets invented or guessed at when the real fetch
doesn't work out.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_EXCERPT_CHARS = 2500
_TIMEOUT_SECONDS = 8.0


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


async def scrape_company_website(*, domain: str | None, website: str | None) -> str | None:
    """Returns a short plain-text excerpt of the company's real homepage,
    or None if there's nothing to fetch or the fetch didn't pan out."""
    url = website or (f"https://{domain}" if domain else None)
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_TIMEOUT_SECONDS), follow_redirects=True
        ) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; LeadPlatformBot/1.0)"})
    except httpx.RequestError as exc:
        logger.info("company_website_scrape_failed", url=url, error=str(exc))
        return None

    if response.status_code >= 400:
        logger.info("company_website_scrape_non_2xx", url=url, status_code=response.status_code)
        return None

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        return None

    text = _extract_text(response.text)
    if not text:
        return None
    return text[:_MAX_EXCERPT_CHARS]
