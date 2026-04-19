"""
Main pipeline entry point for the Automated Senior PM Job Search system.

Module 1: Scrape jobs from all sources
Module 2: Score new jobs using Gemini AI (added in Module 2)
"""

import sys
import logging
import time
from datetime import datetime

import config
import database
from scraper import run_jobspy_scraper, run_greenhouse_scraper, run_lever_scraper
from scorer.job_scorer import score_job

# ──────────────────────────── Logging Setup ────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
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
        "greenhouse": 0,
        "lever": 0,
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

    # [2] Run Greenhouse scraper
    try:
        results["greenhouse"] = run_greenhouse_scraper()
    except Exception as e:
        logger.error("Greenhouse scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"Greenhouse: {e}")

    # [3] Run Lever scraper
    try:
        results["lever"] = run_lever_scraper()
    except Exception as e:
        logger.error("Lever scraper crashed: %s", e, exc_info=True)
        results["errors"].append(f"Lever: {e}")

    # Calculate totals
    results["total_new"] = results["jobspy"] + results["greenhouse"] + results["lever"]
    elapsed = round(time.time() - start_time, 1)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("SCRAPING PIPELINE COMPLETE")
    logger.info("-" * 70)
    logger.info("  JobSpy (LinkedIn/Indeed/Glassdoor/Google/Naukri): %d new jobs", results["jobspy"])
    logger.info("  Greenhouse:   %d new jobs", results["greenhouse"])
    logger.info("  Lever:        %d new jobs", results["lever"])
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
    """
    unscored = database.get_unscored_jobs()
    if not unscored:
        logger.info("No new unscored jobs found.")
        return {"scored": 0, "unscored": 0}

    logger.info("Found %d unscored jobs. Starting evaluation...", len(unscored))
    
    scored_count = 0
    errors = 0

    for job in unscored:
        try:
            logger.info(f"Evaluating: {job['title']} at {job['company']}")
            
            # Score it
            eval_data = score_job(
                job_description=job["description"],
                job_title=job["title"],
                company=job["company"]
            )
            
            # Format lists to JSON strings for DB storage
            import json
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
                
            logger.info(f"  → Score: {score_val:.1f}/5.0 ({label}) | Legitimacy: {eval_data.get('legitimacy')}")
            
        except Exception as e:
            logger.error(f"Failed to score job {job['id']} ({job['title']}): {e}", exc_info=True)
            errors += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info("SCORING PIPELINE COMPLETE")
    logger.info(f"  Successfully scored: {scored_count}")
    logger.info(f"  Errors: {errors}")
    logger.info("=" * 70)

    return {"scored": scored_count, "errors": errors}


def main():
    """Run the full pipeline: Scrape → Score."""
    logger.info("")
    logger.info("AUTOMATED SENIOR PM JOB SEARCH -- Pipeline Run")
    logger.info("   %s", datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"))
    logger.info("")

    # Initialize database
    database.init_db()

    # Step 1: Scrape
    scrape_results = run_scraping_pipeline()

    # Step 2: Score (Module 2 — placeholder for now)
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

    return {
        "scraping": scrape_results,
        "scoring": score_results,
        "stats": stats,
    }


if __name__ == "__main__":
    main()
