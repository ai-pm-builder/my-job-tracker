"""
Daily Telegram digest for the Job Tracker pipeline.

Sends a structured morning summary via Telegram with:
- New jobs found today (count by source)
- Top 5 highest-scored new jobs (with direct links)
- Application funnel summary
- Any warnings (dead jobs, scoring errors)

Requires these env vars:
    TELEGRAM_BOT_TOKEN   — Bot token from @BotFather
    TELEGRAM_CHAT_ID     — Your personal chat ID (get from @userinfobot)

If either is missing the notification is skipped silently.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

import config
import database
from tracker.status_manager import get_funnel_summary

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4096  # Telegram hard limit


# ──────────────────────────── Public API ────────────────────────────

def send_daily_digest(pipeline_results: Optional[dict] = None) -> bool:
    """
    Build and send the daily digest.

    Args:
        pipeline_results: The dict returned by main.main() — used for scrape stats.
                          Pass None to send a stats-only digest.

    Returns:
        True if message sent successfully, False otherwise.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning(
            "digest: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping notification."
        )
        return False

    message = _build_message(pipeline_results)

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("digest: Telegram message sent successfully.")
        return True
    except requests.RequestException as e:
        logger.error("digest: failed to send Telegram message — %s", e)
        return False


# ──────────────────────────── Message Builder ────────────────────────────

def _build_message(pipeline_results: Optional[dict]) -> str:
    """Compose the full digest message."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %d %b %Y")

    parts: list[str] = []

    # ── Header ──
    parts.append(f"<b>Job Tracker Daily Digest</b>")
    parts.append(f"<i>{date_str}</i>")
    parts.append("")

    # ── Scraping Summary ──
    if pipeline_results and "scraping" in pipeline_results:
        sc = pipeline_results["scraping"]
        total = sc.get("total_new", 0)
        parts.append(f"<b>New Jobs Found: {total}</b>")
        parts.append(f"  ATS portals:  {sc.get('ats', 0)}")
        parts.append(f"  Free APIs:    {sc.get('apis', 0)}")
        parts.append(f"  RSS feeds:    {sc.get('rss', 0)}")
        parts.append(f"  JobSpy:       {sc.get('jobspy', 0)}")
        if sc.get("errors"):
            parts.append(f"  Errors: {len(sc['errors'])}")
        parts.append("")

    # ── Top 5 Scored Jobs ──
    top_jobs = _get_top_scored_jobs(limit=5)
    if top_jobs:
        parts.append("<b>Top Matches Today</b>")
        for i, job in enumerate(top_jobs, 1):
            score = job.get("overall_score")
            score_str = f"{score:.1f}/5" if score else "unscored"
            title = _escape(job["title"])
            company = _escape(job.get("company", "Unknown"))
            url = job.get("job_url", "")
            archetype = job.get("archetype", "")
            legitimacy = job.get("legitimacy", "")

            if url:
                line = f'{i}. <a href="{url}">{title}</a> @ {company}'
            else:
                line = f"{i}. {title} @ {company}"

            line += f" [{score_str}]"
            if archetype and archetype != "Unknown":
                line += f" — {archetype}"
            if legitimacy == "Suspicious":
                line += " ⚠️"
            parts.append(line)
        parts.append("")

    # ── Application Funnel ──
    funnel = get_funnel_summary()
    total_tracked = sum(funnel.values())
    if total_tracked > 0:
        parts.append("<b>Application Funnel</b>")
        funnel_display = [
            ("new",       "New"),
            ("evaluated", "Evaluated"),
            ("applied",   "Applied"),
            ("responded", "Responded"),
            ("interview", "Interview"),
            ("offer",     "Offer"),
            ("rejected",  "Rejected"),
            ("skipped",   "Skipped"),
        ]
        for key, label in funnel_display:
            count = funnel.get(key, 0)
            if count > 0:
                parts.append(f"  {label}: {count}")
        parts.append("")

    # ── DB Stats ──
    try:
        stats = database.get_job_stats()
        parts.append("<b>Database</b>")
        parts.append(f"  Total jobs:    {stats['total_jobs']}")
        parts.append(f"  Scored:        {stats['scored_jobs']}")
        avg = stats.get("avg_score", 0)
        if avg:
            parts.append(f"  Avg score:     {avg:.1f}/5.0")
        if stats.get("high_match", 0) > 0:
            parts.append(f"  Strong matches: {stats['high_match']}")
    except Exception as e:
        logger.warning("digest: could not fetch DB stats — %s", e)

    # ── Footer ──
    parts.append("")
    parts.append("<i>Job Tracker v2 — auto digest</i>")

    message = "\n".join(parts)

    # Truncate if over Telegram limit
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[: MAX_MESSAGE_LENGTH - 20] + "\n...(truncated)"

    return message


# ──────────────────────────── Helpers ────────────────────────────

def _get_top_scored_jobs(limit: int = 5) -> list[dict]:
    """Get the top N scored jobs from today's scrape."""
    import sqlite3
    from config import DB_PATH

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT j.id, j.title, j.company, j.job_url,
                   s.overall_score, s.archetype, s.legitimacy
            FROM jobs j
            JOIN scores s ON j.id = s.job_id
            WHERE DATE(j.date_scraped) = DATE('now')
            ORDER BY s.overall_score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.warning("digest: could not query top jobs — %s", e)
        return []


def _escape(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
