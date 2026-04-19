"""
Custom scraper for Lever-hosted career pages.
Scrapes jobs.lever.co/{company} for PM-related job postings.
"""

import logging
import requests

import database
from scraper.company_list import LEVER_COMPANIES, PM_KEYWORDS

logger = logging.getLogger(__name__)

# Lever also exposes a JSON API for job postings
LEVER_API_URL = "https://api.lever.co/v0/postings/{slug}"

REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


def _is_pm_role(title: str) -> bool:
    """Check if a job title matches PM-related keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in PM_KEYWORDS)


def _build_description(posting: dict) -> str:
    """Build a plain text description from Lever posting data."""
    parts = []

    # Lever stores description in "descriptionPlain" or structured "lists"
    desc = posting.get("descriptionPlain", "")
    if desc:
        parts.append(desc.strip())

    # Additional sections (Requirements, Qualifications, etc.)
    lists = posting.get("lists", [])
    for lst in lists:
        section_title = lst.get("text", "")
        items = lst.get("content", "")
        if section_title:
            parts.append(f"\n{section_title}")
        if items:
            # Items is HTML, extract text
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(items, "html.parser")
            parts.append(soup.get_text(separator="\n", strip=True))

    # Additional info
    additional = posting.get("additional", "")
    if additional:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(additional, "html.parser")
        parts.append(soup.get_text(separator="\n", strip=True))

    return "\n\n".join(parts)


def _scrape_lever_company(company_name: str, slug: str) -> int:
    """
    Scrape a single Lever company's job board via their JSON API.
    Returns count of new jobs inserted.
    """
    url = LEVER_API_URL.format(slug=slug)
    new_count = 0

    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        postings = response.json()

        if not isinstance(postings, list):
            logger.warning("  %s: Unexpected Lever response format", company_name)
            return 0

        logger.info("  %s: Found %d total jobs on Lever", company_name, len(postings))

        for posting in postings:
            title = posting.get("text", "")
            if not _is_pm_role(title):
                continue

            # Extract location
            categories = posting.get("categories", {})
            location = categories.get("location", "")
            commitment = categories.get("commitment", "")

            # Build URL and description
            job_url = posting.get("hostedUrl", posting.get("applyUrl", ""))
            description = _build_description(posting)
            created_at = posting.get("createdAt", None)

            # Convert epoch ms to date string
            date_posted = None
            if created_at:
                from datetime import datetime
                try:
                    date_posted = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d")
                except (OSError, ValueError):
                    pass

            is_remote = "remote" in location.lower() if location else False

            inserted_id = database.insert_job(
                title=title,
                company=company_name,
                location=location,
                description=description,
                job_url=job_url,
                source="lever",
                job_type=commitment or None,
                date_posted=date_posted,
                is_remote=is_remote,
            )
            if inserted_id is not None:
                new_count += 1

    except requests.exceptions.RequestException as e:
        logger.warning("  %s: Lever request failed — %s", company_name, e)
    except Exception as e:
        logger.error("  %s: Lever scrape error — %s", company_name, e)

    return new_count


def run_lever_scraper() -> int:
    """
    Scrape all configured Lever companies.
    Returns total count of new jobs inserted.
    """
    logger.info("=" * 60)
    logger.info("STARTING LEVER SCRAPER (%d companies)", len(LEVER_COMPANIES))
    logger.info("=" * 60)

    total_new = 0
    for company_name, slug in LEVER_COMPANIES:
        new = _scrape_lever_company(company_name, slug)
        total_new += new
        if new > 0:
            logger.info("  -> %s: %d new PM jobs added", company_name, new)

    logger.info("LEVER SCRAPER COMPLETE — %d new PM jobs added", total_new)
    return total_new
