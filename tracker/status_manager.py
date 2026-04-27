"""
Application status tracking for the Job Tracker pipeline.

Manages the full application funnel:
  new -> evaluated -> applied -> responded -> interview -> offer | rejected | skipped

This module handles:
- Adding the `application_status` + `status_updated_at` columns to the DB (migration-safe)
- Functions to update and query job status
- A summary view of the funnel for the daily digest
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

# ──────────────────────────── Constants ────────────────────────────

VALID_STATUSES = {
    "new",           # Scraped, not yet evaluated
    "evaluated",     # AI scored — waiting for manual review
    "applied",       # You submitted an application
    "responded",     # Company reached out
    "interview",     # Interview scheduled or in progress
    "offer",         # Offer received
    "rejected",      # Rejected / no response after 4+ weeks
    "skipped",       # Manually dismissed (score too low, role not relevant)
}

DEFAULT_STATUS = "new"


# ──────────────────────────── Schema Migration ────────────────────────────

def ensure_status_columns() -> None:
    """
    Add application_status and status_updated_at to the jobs table if they don't exist.
    This is idempotent — safe to call on every startup.
    """
    conn = _get_conn()
    # Check existing columns
    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}

    if "application_status" not in existing:
        conn.execute(
            f"ALTER TABLE jobs ADD COLUMN application_status TEXT DEFAULT '{DEFAULT_STATUS}'"
        )
        logger.info("tracker: added 'application_status' column to jobs table.")

    if "status_updated_at" not in existing:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN status_updated_at TEXT"
        )
        logger.info("tracker: added 'status_updated_at' column to jobs table.")

    conn.commit()
    conn.close()


# ──────────────────────────── Status Operations ────────────────────────────

def set_status(job_id: int, status: str, note: str = "") -> bool:
    """
    Update the application status for a job.

    Args:
        job_id:  The job ID (from the jobs table).
        status:  One of VALID_STATUSES.
        note:    Optional note to log alongside the transition.

    Returns:
        True if updated, False if job not found or status invalid.
    """
    if status not in VALID_STATUSES:
        logger.error(
            "tracker: invalid status '%s'. Must be one of: %s",
            status,
            ", ".join(sorted(VALID_STATUSES)),
        )
        return False

    conn = _get_conn()
    now = datetime.utcnow().isoformat()

    rows_affected = conn.execute(
        "UPDATE jobs SET application_status = ?, status_updated_at = ? WHERE id = ?",
        (status, now, job_id),
    ).rowcount

    conn.commit()
    conn.close()

    if rows_affected == 0:
        logger.warning("tracker: job ID %d not found.", job_id)
        return False

    log_msg = f"tracker: job #{job_id} -> '{status}'"
    if note:
        log_msg += f" ({note})"
    logger.info(log_msg)
    return True


def get_status(job_id: int) -> Optional[str]:
    """Return the current application status for a job, or None if not found."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT application_status FROM jobs WHERE id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_funnel_summary() -> dict:
    """
    Return a count breakdown of all statuses for the digest / analytics.

    Returns:
        {
          "new": 42,
          "evaluated": 18,
          "applied": 7,
          ...
        }
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT COALESCE(application_status, 'new') as status, COUNT(*) as cnt
        FROM jobs
        GROUP BY status
        """
    ).fetchall()
    conn.close()

    summary = {s: 0 for s in VALID_STATUSES}
    for row in rows:
        status = row[0] if row[0] in VALID_STATUSES else "new"
        summary[status] = row[1]
    return summary


def get_jobs_by_status(status: str, limit: int = 50) -> list[dict]:
    """Return jobs with a specific application status, most recent first."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT j.id, j.title, j.company, j.location, j.job_url,
               j.application_status, j.status_updated_at, j.date_scraped,
               s.overall_score, s.archetype, s.legitimacy
        FROM jobs j
        LEFT JOIN scores s ON j.id = s.job_id
        WHERE COALESCE(j.application_status, 'new') = ?
        ORDER BY j.date_scraped DESC
        LIMIT ?
        """,
        (status, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_evaluated(job_id: int) -> bool:
    """Convenience: mark a job as evaluated after scoring."""
    return set_status(job_id, "evaluated")


def mark_applied(job_id: int, note: str = "") -> bool:
    """Convenience: mark that you submitted an application."""
    return set_status(job_id, "applied", note)


def mark_skipped(job_id: int, reason: str = "") -> bool:
    """Convenience: dismiss a low-quality job."""
    return set_status(job_id, "skipped", reason)


# ──────────────────────────── Private ────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
