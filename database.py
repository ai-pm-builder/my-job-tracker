"""
SQLite database operations for the Job Tracker system.
Handles schema creation and CRUD for jobs, scores, and tailored resumes.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with Row factory for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema. Safe to call multiple times."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # ── Jobs Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            description TEXT,
            job_url TEXT,
            source TEXT,
            job_type TEXT,
            salary TEXT,
            date_posted TEXT,
            date_scraped TEXT NOT NULL DEFAULT (datetime('now')),
            url_hash TEXT UNIQUE NOT NULL,
            is_remote INTEGER DEFAULT 0,
            company_url TEXT,
            logo_url TEXT,
            raw_data TEXT
        )
    """)
    
    # ── Scores Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL UNIQUE,
            overall_score REAL NOT NULL,
            cv_match REAL,
            north_star_alignment REAL,
            compensation REAL,
            cultural_signals REAL,
            red_flags REAL,
            archetype TEXT,
            legitimacy TEXT DEFAULT 'Proceed with Caution',
            reasoning TEXT,
            matching_skills TEXT,
            skill_gaps TEXT,
            gap_analysis TEXT,
            personalization_plan TEXT,
            interview_prep TEXT,
            scored_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    
    # ── Tailored Resumes Table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tailored_resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            tailored_summary TEXT,
            tailored_skills TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    
    # ── Indexes ──
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url_hash ON jobs(url_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date_scraped ON jobs(date_scraped)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_job_id ON scores(job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_overall ON scores(overall_score)")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", DB_PATH)


def generate_url_hash(job_url: str, title: str) -> str:
    """Generate a unique hash from job URL + title for deduplication."""
    raw = f"{job_url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def job_exists(url_hash: str) -> bool:
    """Check if a job with the given hash already exists."""
    conn = get_connection()
    result = conn.execute(
        "SELECT 1 FROM jobs WHERE url_hash = ?", (url_hash,)
    ).fetchone()
    conn.close()
    return result is not None


def insert_job(
    title: str,
    company: str,
    location: str,
    description: str,
    job_url: str,
    source: str,
    job_type: str = None,
    salary: str = None,
    date_posted: str = None,
    is_remote: bool = False,
    company_url: str = None,
    logo_url: str = None,
    raw_data: str = None,
) -> Optional[int]:
    """
    Insert a new job into the database. Returns the job ID, or None if duplicate.
    """
    url_hash = generate_url_hash(job_url or "", title or "")
    
    if job_exists(url_hash):
        logger.debug("Skipping duplicate: %s at %s", title, company)
        return None
    
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO jobs (title, company, location, description, job_url, source,
                              job_type, salary, date_posted, url_hash, is_remote,
                              company_url, logo_url, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title, company, location, description, job_url, source,
                job_type, salary, date_posted, url_hash, int(is_remote),
                company_url, logo_url, raw_data,
            ),
        )
        conn.commit()
        job_id = cursor.lastrowid
        logger.info("Inserted job #%d: %s at %s [%s]", job_id, title, company, source)
        return job_id
    except sqlite3.IntegrityError:
        logger.debug("Duplicate hash for: %s at %s", title, company)
        return None
    finally:
        conn.close()


def insert_score(
    job_id: int,
    overall_score: float,
    cv_match: float = None,
    north_star_alignment: float = None,
    compensation: float = None,
    cultural_signals: float = None,
    red_flags: float = None,
    archetype: str = None,
    legitimacy: str = "Proceed with Caution",
    reasoning: str = None,
    matching_skills: str = None,
    skill_gaps: str = None,
    gap_analysis: str = None,
    personalization_plan: str = None,
    interview_prep: str = None,
) -> int:
    """Insert or update a score for a job."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO scores
            (job_id, overall_score, cv_match, north_star_alignment, compensation,
             cultural_signals, red_flags, archetype, legitimacy, reasoning,
             matching_skills, skill_gaps, gap_analysis, personalization_plan, interview_prep)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id, overall_score, cv_match, north_star_alignment, compensation,
            cultural_signals, red_flags, archetype, legitimacy, reasoning,
            matching_skills, skill_gaps, gap_analysis, personalization_plan, interview_prep
        ),
    )
    conn.commit()
    score_id = cursor.lastrowid
    conn.close()
    return score_id


def insert_tailored_resume(
    job_id: int,
    file_path: str,
    tailored_summary: str = None,
    tailored_skills: str = None,
) -> int:
    """Record a generated tailored resume."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO tailored_resumes (job_id, file_path, tailored_summary, tailored_skills)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, file_path, tailored_summary, tailored_skills),
    )
    conn.commit()
    resume_id = cursor.lastrowid
    conn.close()
    return resume_id


def get_all_jobs(limit: int = 500, offset: int = 0) -> list[dict]:
    """Get all jobs with their scores, ordered by score descending."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT j.*, s.overall_score, s.cv_match, s.north_star_alignment,
               s.compensation, s.cultural_signals, s.red_flags,
               s.archetype, s.legitimacy, s.reasoning,
               s.matching_skills, s.skill_gaps, s.gap_analysis,
               s.personalization_plan, s.interview_prep, s.scored_at
        FROM jobs j
        LEFT JOIN scores s ON j.id = s.job_id
        ORDER BY COALESCE(s.overall_score, -1) DESC, j.date_scraped DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_unscored_jobs() -> list[dict]:
    """Get jobs that haven't been scored yet."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT j.*
        FROM jobs j
        LEFT JOIN scores s ON j.id = s.job_id
        WHERE s.id IS NULL
        ORDER BY j.date_scraped DESC
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_job_by_id(job_id: int) -> Optional[dict]:
    """Get a single job with its score."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT j.*, s.overall_score, s.cv_match, s.north_star_alignment,
               s.compensation, s.cultural_signals, s.red_flags,
               s.archetype, s.legitimacy, s.reasoning,
               s.matching_skills, s.skill_gaps, s.gap_analysis,
               s.personalization_plan, s.interview_prep, s.scored_at
        FROM jobs j
        LEFT JOIN scores s ON j.id = s.job_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tailored_resumes(job_id: int) -> list[dict]:
    """Get all tailored resumes for a given job."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tailored_resumes WHERE job_id = ? ORDER BY created_at DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_job_stats() -> dict:
    """Get aggregate stats for the dashboard."""
    conn = get_connection()
    stats = {}
    
    stats["total_jobs"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    stats["scored_jobs"] = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    stats["tailored_resumes"] = conn.execute("SELECT COUNT(*) FROM tailored_resumes").fetchone()[0]
    
    avg_row = conn.execute("SELECT AVG(overall_score) FROM scores").fetchone()
    stats["avg_score"] = round(avg_row[0], 1) if avg_row[0] else 0
    
    stats["high_match"] = conn.execute(
        "SELECT COUNT(*) FROM scores WHERE overall_score >= 4.5"
    ).fetchone()[0]
    
    stats["good_match"] = conn.execute(
        "SELECT COUNT(*) FROM scores WHERE overall_score >= 4.0 AND overall_score < 4.5"
    ).fetchone()[0]
    
    # Jobs by source
    source_rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM jobs GROUP BY source ORDER BY count DESC"
    ).fetchall()
    stats["by_source"] = {row["source"]: row["count"] for row in source_rows}
    
    # Jobs by date (last 7 days)
    date_rows = conn.execute(
        """
        SELECT DATE(date_scraped) as day, COUNT(*) as count
        FROM jobs
        WHERE date_scraped >= datetime('now', '-7 days')
        GROUP BY day ORDER BY day
        """
    ).fetchall()
    stats["by_date"] = {row["day"]: row["count"] for row in date_rows}
    
    conn.close()
    return stats


# Initialize DB on import
init_db()
