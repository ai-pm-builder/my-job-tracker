"""
Job liveness checker for the Job Tracker pipeline.

Verifies that a job posting URL is still active before spending Gemini tokens scoring it.
Catches:
- HTTP 404 / 410 / 403 responses
- Redirect to a generic careers page (ATS-style "position no longer available")
- "Position filled" / "no longer accepting" keyword detection in the page body

Strategy:
1. Fast HEAD request first (just check status code)
2. If OK, quick GET and scan body for "dead listing" signals
3. Timeout: 8 seconds — skip the check if server is unresponsive

Usage:
    from checker.liveness import is_live

    if is_live(job_url):
        score_job(...)
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# ──────────────────────────── Constants ────────────────────────────

REQUEST_TIMEOUT = 8  # seconds

DEAD_SIGNALS: list[str] = [
    "no longer accepting",
    "position has been filled",
    "job is no longer available",
    "this job is no longer",
    "posting has expired",
    "this position is no longer",
    "this opening is no longer",
    "application is closed",
    "we are no longer accepting",
    "404",
    "page not found",
    "job not found",
]

# ATS "no job" redirect patterns — if the final URL matches, listing is gone
DEAD_URL_PATTERNS: list[str] = [
    r"/jobs/?$",               # redirected to blank jobs list
    r"/careers/?$",
    r"error=true",
    r"notfound",
    r"not-found",
    r"job-not-found",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ──────────────────────────── Core Function ────────────────────────────

def is_live(job_url: str, timeout: int = REQUEST_TIMEOUT) -> bool:
    """
    Return True if the job posting appears to still be active, False otherwise.

    Conservatively returns True on network errors (don't skip a job just because
    the check timed out — let the scorer handle it).
    """
    if not job_url or not job_url.startswith("http"):
        logger.debug("liveness: no valid URL for check — assuming live.")
        return True

    try:
        # Step 1: HEAD request — fast status check
        head_resp = requests.head(
            job_url, headers=HEADERS, timeout=timeout, allow_redirects=True
        )

        # Hard-dead status codes
        if head_resp.status_code in (404, 410):
            logger.info("liveness: DEAD (HTTP %d) — %s", head_resp.status_code, job_url)
            return False

        # Check if redirect landed on a dead URL pattern
        final_url = head_resp.url
        if _matches_dead_url(final_url):
            logger.info("liveness: DEAD (redirect to '%s') — %s", final_url, job_url)
            return False

        # Step 2: GET body for keyword signals (only for 200-range responses)
        if head_resp.status_code < 300:
            get_resp = requests.get(
                job_url, headers=HEADERS, timeout=timeout, allow_redirects=True,
                stream=True,  # don't download the entire page
            )
            # Read only the first 8KB — enough to detect dead signals in <title> / header
            body_snippet = get_resp.raw.read(8192).decode("utf-8", errors="replace").lower()

            if _matches_dead_body(body_snippet):
                logger.info("liveness: DEAD (dead signal in body) — %s", job_url)
                return False

        logger.debug("liveness: LIVE — %s", job_url)
        return True

    except RequestException as e:
        logger.warning("liveness: check failed for %s (%s) — assuming live.", job_url, e)
        return True  # Conservative: assume live on network error


def check_batch(
    jobs: list[dict],
    url_field: str = "job_url",
    skip_if_no_url: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Check a batch of job dicts for liveness.

    Returns:
        (live_jobs, dead_jobs) — two lists of job dicts.
    """
    live, dead = [], []
    for job in jobs:
        url = job.get(url_field, "")
        if not url and skip_if_no_url:
            dead.append(job)
            continue
        if is_live(url):
            live.append(job)
        else:
            dead.append(job)
        time.sleep(0.3)  # Polite delay between checks

    logger.info(
        "liveness: batch check complete — %d live, %d dead.", len(live), len(dead)
    )
    return live, dead


# ──────────────────────────── Helpers ────────────────────────────

def _matches_dead_url(url: str) -> bool:
    url_lower = url.lower()
    return any(re.search(pat, url_lower) for pat in DEAD_URL_PATTERNS)


def _matches_dead_body(body: str) -> bool:
    return any(signal in body for signal in DEAD_SIGNALS)
