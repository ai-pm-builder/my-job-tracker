"""
Custom scraper for Greenhouse-hosted career pages.
Scrapes boards.greenhouse.io/{company} for PM-related job postings.
"""

import logging
import requests
from bs4 import BeautifulSoup

import database
from scraper.company_list import GREENHOUSE_COMPANIES, PM_KEYWORDS

logger = logging.getLogger(__name__)

# Greenhouse exposes a JSON API for job boards
GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
GREENHOUSE_JOB_URL = "https://boards.greenhouse.io/{slug}/jobs/{job_id}"

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


def _extract_description(content: str) -> str:
    """Extract plain text from Greenhouse HTML content."""
    if not content:
        return ""
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def _scrape_greenhouse_company(company_name: str, slug: str) -> int:
    """
    Scrape a single Greenhouse company's job board via their JSON API.
    Returns count of new jobs inserted.
    """
    url = GREENHOUSE_API_URL.format(slug=slug)
    new_count = 0

    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])

        logger.info("  %s: Found %d total jobs on Greenhouse", company_name, len(jobs))

        for job in jobs:
            title = job.get("title", "")
            if not _is_pm_role(title):
                continue

            job_id = job.get("id", "")
            location_data = job.get("location", {})
            location = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)
            content = job.get("content", "")
            description = _extract_description(content)
            job_url = job.get("absolute_url", GREENHOUSE_JOB_URL.format(slug=slug, job_id=job_id))
            updated_at = job.get("updated_at", "")

            inserted_id = database.insert_job(
                title=title,
                company=company_name,
                location=location,
                description=description,
                job_url=job_url,
                source="greenhouse",
                date_posted=updated_at[:10] if updated_at else None,
            )
            if inserted_id is not None:
                new_count += 1

    except requests.exceptions.RequestException as e:
        logger.warning("  %s: Greenhouse request failed — %s", company_name, e)
    except Exception as e:
        logger.error("  %s: Greenhouse scrape error — %s", company_name, e)

    return new_count


def run_greenhouse_scraper() -> int:
    """
    Scrape all configured Greenhouse companies.
    Returns total count of new jobs inserted.
    """
    logger.info("=" * 60)
    logger.info("STARTING GREENHOUSE SCRAPER (%d companies)", len(GREENHOUSE_COMPANIES))
    logger.info("=" * 60)

    total_new = 0
    for company_name, slug in GREENHOUSE_COMPANIES:
        new = _scrape_greenhouse_company(company_name, slug)
        total_new += new
        if new > 0:
            logger.info("  -> %s: %d new PM jobs added", company_name, new)

    logger.info("GREENHOUSE SCRAPER COMPLETE — %d new PM jobs added", total_new)
    return total_new
