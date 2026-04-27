"""
In-memory deduplication engine for the Job Tracker pipeline.

Filters jobs BEFORE they hit the database to avoid:
1. Redundant INSERT attempts + IntegrityError on duplicate URLs (same job, same source)
2. Cross-source duplicates: same role posted on Greenhouse AND LinkedIn (different URL, same job)

Usage:
    from dedup import DeduplicationEngine
    dedup = DeduplicationEngine()
    dedup.preload_from_db()

    clean_jobs = dedup.filter(raw_jobs_list)
"""

import hashlib
import logging
import re
import sqlite3
from typing import Optional

import config
from config import DB_PATH

logger = logging.getLogger(__name__)


def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation for fuzzy comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _url_hash(job_url: str, title: str) -> str:
    """Same hash logic as database.generate_url_hash."""
    raw = f"{job_url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _title_company_key(title: str, company: str) -> str:
    """Fuzzy dedup key: normalised title + company slug."""
    return f"{_normalise(title)}|{_normalise(company)}"


class DeduplicationEngine:
    """
    Dual-layer deduplication:
    - Layer 1: exact URL hash (catches same-source repeats)
    - Layer 2: normalised title+company (catches cross-source dupes)
    """

    def __init__(self):
        self._url_hashes: set[str] = set()
        self._title_company_keys: set[str] = set()
        self._preloaded = False

    # ──────────────────────────── Preload ────────────────────────────

    def preload_from_db(self) -> int:
        """
        Load existing URL hashes and title+company combos from the database.
        Call this once at pipeline start. Returns the number of entries loaded.
        """
        try:
            conn = sqlite3.connect(str(DB_PATH))
            rows = conn.execute(
                "SELECT url_hash, title, company FROM jobs"
            ).fetchall()
            conn.close()
        except sqlite3.OperationalError:
            logger.warning("dedup: DB not yet initialised — starting with empty sets.")
            rows = []

        for url_hash, title, company in rows:
            self._url_hashes.add(url_hash)
            if title and company:
                self._title_company_keys.add(_title_company_key(title, company))

        self._preloaded = True
        logger.info(
            "dedup: pre-loaded %d URL hashes, %d title+company keys from DB.",
            len(self._url_hashes),
            len(self._title_company_keys),
        )
        return len(rows)

    # ──────────────────────────── Core logic ────────────────────────────

    def is_duplicate(self, job: dict) -> bool:
        """Return True if this job is a duplicate and should be skipped."""
        url = job.get("job_url") or ""
        title = job.get("title") or ""
        company = job.get("company") or ""

        # Layer 1 — URL hash
        h = _url_hash(url, title)
        if h in self._url_hashes:
            logger.debug("dedup[URL]: skipping '%s' @ %s", title, company)
            return True

        # Layer 2 — title+company
        if title and company:
            key = _title_company_key(title, company)
            if key in self._title_company_keys:
                logger.debug("dedup[title+co]: skipping '%s' @ %s", title, company)
                return True

        return False

    def register(self, job: dict) -> None:
        """
        Mark a job as seen so later jobs in the same batch are deduplicated.
        Call this after the job is accepted (before DB insert).
        """
        url = job.get("job_url") or ""
        title = job.get("title") or ""
        company = job.get("company") or ""

        self._url_hashes.add(_url_hash(url, title))
        if title and company:
            self._title_company_keys.add(_title_company_key(title, company))

    def filter(self, jobs: list[dict]) -> list[dict]:
        """
        Filter a list of job dicts, returning only those that are NOT duplicates.
        Also registers accepted jobs so intra-batch duplicates are caught.
        """
        if not self._preloaded:
            logger.warning("dedup: preload_from_db() was not called — cross-run dedup won't work.")

        accepted = []
        skipped = 0
        for job in jobs:
            if self.is_duplicate(job):
                skipped += 1
            else:
                self.register(job)
                accepted.append(job)

        if skipped:
            logger.info("dedup: filtered out %d duplicate(s), %d unique remain.", skipped, len(accepted))

        return accepted
