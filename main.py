"""
Main pipeline entry point for the Automated Senior PM Job Search system.

Module 1: Scrape jobs from all sources
Module 2: Score new jobs using Gemini AI (added in Module 2)
"""

import sys
import logging
import time
from datetime import datetime

import json

import config
import database
from scraper import run_jobspy_scraper, run_ats_scraper, run_api_scraper, run_rss_scraper
from scorer.job_scorer import score_job
from dedup import DeduplicationEngine
from checker.liveness import is_live
from tracker.status_manager import ensure_status_columns, mark_evaluated
from notifications.digest import send_daily_digest

# ──────────────────────────── Logging Setup ────────────────────────────
# Use a UTF-8-safe stream handler to avoid cp1252 encoding errors on Windows
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        _stdout_handler,
        logging.FileHandler(
            config.DATA_DIR / "pipeline.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def run_scraping_pipeline() -> dict:
    """
    Run all scrapers and return summary stats.
    """
    logger.info("=" * 70)
    logger.info("JOB SCRAPING PIPELINE STARTED — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 70)

    results = {
        "jobspy": 0,
        "ats": 0,
        "apis": 0,
        "rss": 0,
        "total_new": 0,
        "errors": [],
    }

    start_time = time.time()

    # [1] Run python-jobspy scraper (LinkedIn, Indeed, Glassdoor, Google, Naukri)
    try:
        results["jobspy"] = run_jobspy_scraper()
    except Exception as e:
        logger.error("JobSpy scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"JobSpy: {e}")

    # [2] Run Unified ATS scraper (Greenhouse, Lever, Ashby, etc.)
    try:
        results["ats"] = run_ats_scraper()
    except Exception as e:
        logger.error("ATS scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"ATS: {e}")

    # [4] Run Free API scraper
    try:
        results["apis"] = run_api_scraper()
    except Exception as e:
        logger.error("API scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"APIs: {e}")

    # [5] Run RSS scraper
    try:
        results["rss"] = run_rss_scraper()
    except Exception as e:
        logger.error("RSS scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"RSS: {e}")

    # Calculate totals
    results["total_new"] = results.get("jobspy", 0) + results.get("ats", 0) + results.get("apis", 0) + results.get("rss", 0)
    elapsed = round(time.time() - start_time, 1)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("SCRAPING PIPELINE COMPLETE")
    logger.info("-" * 70)
    logger.info("  JobSpy:       %d new jobs", results.get("jobspy", 0))
    logger.info("  Unified ATS:  %d new jobs", results.get("ats", 0))
    logger.info("  Free APIs:    %d new jobs", results.get("apis", 0))
    logger.info("  RSS Feeds:    %d new jobs", results.get("rss", 0))
    logger.info("-" * 70)
    logger.info("  TOTAL NEW:    %d jobs", results["total_new"])
    logger.info("  Time elapsed: %s seconds", elapsed)
    if results["errors"]:
        logger.warning("  Errors: %s", "; ".join(results["errors"]))
    logger.info("=" * 70)

    return results


def run_scoring_pipeline() -> dict:
    """
    Score all unscored jobs using Module 2's career-ops style evaluation.
    Runs a liveness check first to skip dead listings.
    """
    unscored = database.get_unscored_jobs()
    if not unscored:
        logger.info("No new unscored jobs found.")
        return {"scored": 0, "skipped_dead": 0, "errors": 0}

    logger.info("Found %d unscored jobs. Checking liveness...", len(unscored))

    # Liveness filter — skip jobs whose URLs are dead
    live_jobs = []
    dead_count = 0
    for job in unscored:
        if is_live(job.get("job_url", "")):
            live_jobs.append(job)
        else:
            dead_count += 1
            logger.info("Skipping dead listing: %s at %s", job["title"], job["company"])

    if dead_count:
        logger.info("Liveness check: %d dead listing(s) skipped.", dead_count)

    if not live_jobs:
        logger.info("No live jobs to score after liveness check.")
        return {"scored": 0, "skipped_dead": dead_count, "errors": 0}

    logger.info("Starting evaluation of %d live jobs...", len(live_jobs))
    
    scored_count = 0
    errors = 0

    for job in live_jobs:
        try:
            logger.info(f"Evaluating: {job['title']} at {job['company']}")
            
            # Score it
            eval_data = score_job(
                job_description=job["description"],
                job_title=job["title"],
                company=job["company"]
            )
            
            # Format lists to JSON strings for DB storage
            matching_skills_str = json.dumps(eval_data.get("matching_skills", []))
            skill_gaps_str = json.dumps(eval_data.get("skill_gaps", []))
            
            # Insert into database
            database.insert_score(
                job_id=job["id"],
                overall_score=eval_data["overall_score"],
                cv_match=eval_data["cv_match"],
                north_star_alignment=eval_data["north_star_alignment"],
                compensation=eval_data["compensation"],
                cultural_signals=eval_data["cultural_signals"],
                red_flags=eval_data["red_flags"],
                archetype=eval_data.get("archetype", "Unknown"),
                legitimacy=eval_data.get("legitimacy", "Proceed with Caution"),
                reasoning=eval_data["reasoning"],
                matching_skills=matching_skills_str,
                skill_gaps=skill_gaps_str,
                gap_analysis=eval_data.get("gap_analysis", ""),
                personalization_plan=eval_data.get("personalization_plan", ""),
                interview_prep=eval_data.get("interview_prep", "")
            )
            
            scored_count += 1
            
            # Log result seamlessly
            score_val = eval_data["overall_score"]
            label = "🔴 Weak"
            if score_val >= config.STRONG_MATCH_THRESHOLD:
                label = "🟢 Strong Match"
            elif score_val >= config.GOOD_MATCH_THRESHOLD:
                label = "🔵 Good Match"
            elif score_val >= config.SCORE_THRESHOLD:
                label = "🟡 Decent"
                
            score_label_text = label.encode("ascii", errors="replace").decode("ascii")
            logger.info("  -> Score: %.1f/5.0 (%s) | Legitimacy: %s",
                        score_val, score_label_text, eval_data.get('legitimacy'))

            # Mark job as evaluated in the funnel
            mark_evaluated(job["id"])
            
        except Exception as e:
            logger.error(f"Failed to score job {job['id']} ({job['title']}): {e}", exc_info=True)
            errors += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info("SCORING PIPELINE COMPLETE")
    logger.info(f"  Successfully scored: {scored_count}")
    logger.info(f"  Errors: {errors}")
    logger.info("=" * 70)

    return {"scored": scored_count, "skipped_dead": dead_count, "errors": errors}


def main():
    """Run the full pipeline: Scrape → Score."""
    logger.info("")
    logger.info("AUTOMATED SENIOR PM JOB SEARCH -- Pipeline Run")
    logger.info("   %s", datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"))
    logger.info("")

    # Initialize database
    database.init_db()

    # Run DB migrations for new columns
    ensure_status_columns()

    # Preload dedup engine from DB (cross-run deduplication)
    dedup = DeduplicationEngine()
    dedup.preload_from_db()

    # Step 1: Scrape
    scrape_results = run_scraping_pipeline()

    # Step 2: Score with liveness check
    score_results = run_scoring_pipeline()

    # Final stats
    stats = database.get_job_stats()
    logger.info("")
    logger.info("DATABASE STATS:")
    logger.info("   Total jobs:      %d", stats["total_jobs"])
    logger.info("   Scored jobs:     %d", stats["scored_jobs"])
    logger.info("   Tailored resumes:%d", stats["tailored_resumes"])
    logger.info("   Avg score:       %s", stats["avg_score"])
    logger.info("")

    pipeline_output = {
        "scraping": scrape_results,
        "scoring": score_results,
        "stats": stats,
    }
    return pipeline_output


if __name__ == "__main__":
    results = main()
    # Send Telegram digest at the end of every run
    send_daily_digest(pipeline_results=results)
