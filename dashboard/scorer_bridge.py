"""
scorer_bridge.py — On-demand scoring bridge for the Streamlit dashboard.

Wraps scorer.job_scorer.score_job() with:
  • A liveness check (warns but does NOT block scoring)
  • DB persistence via database.insert_score()
  • Funnel update via tracker.status_manager.mark_evaluated()
"""

import json
import logging
import sys
from pathlib import Path

# ── Ensure project root is on sys.path ──────────────────────────────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database
from scorer.job_scorer import score_job
from checker.liveness import is_live
from tracker.status_manager import mark_evaluated

logger = logging.getLogger(__name__)


def score_job_on_demand(job: dict) -> dict:
    """
    Score a single unscored job and persist the result to the database.

    Performs a liveness check first — if the URL appears dead, a warning is
    returned but scoring continues regardless (Option B behavior).

    Args:
        job: A job dict as returned by database.get_filtered_jobs() or
             database.get_unscored_jobs().

    Returns:
        A dict with:
          "eval_data"        – full JobEvaluation dict, or None on failure
          "liveness_warning" – str message if URL appears dead, else None
          "success"          – True if scored and saved successfully
          "error"            – str error message, or None
    """
    result: dict = {
        "eval_data": None,
        "liveness_warning": None,
        "success": False,
        "error": None,
    }

    job_id = job.get("id")
    job_url = job.get("job_url", "")

    # ── Liveness check — warn but never block ───────────────────────────────
    if job_url:
        try:
            if not is_live(job_url):
                snippet = (job_url[:60] + "…") if len(job_url) > 60 else job_url
                result["liveness_warning"] = (
                    f"The job posting URL may be dead or unreachable ({snippet}). "
                    "Scoring will proceed anyway."
                )
                logger.warning(
                    "Liveness check failed for job %d — URL: %s", job_id, job_url
                )
        except Exception as liveness_err:
            # Never let a liveness check crash the scoring flow
            logger.debug("Liveness check error for job %d: %s", job_id, liveness_err)

    # ── Call the AI scorer ───────────────────────────────────────────────────
    try:
        eval_data = score_job(
            job_description=job.get("description", ""),
            job_title=job.get("title", ""),
            company=job.get("company", ""),
        )
    except Exception as e:
        logger.error(
            "score_job_on_demand: AI scoring failed for job %d (%s): %s",
            job_id, job.get("title", "?"), e,
            exc_info=True,
        )
        result["error"] = f"AI scoring error: {e}"
        return result

    # ── Persist score to DB ──────────────────────────────────────────────────
    try:
        database.insert_score(
            job_id=job_id,
            overall_score=eval_data["overall_score"],
            cv_match=eval_data.get("cv_match"),
            north_star_alignment=eval_data.get("north_star_alignment"),
            compensation=eval_data.get("compensation"),
            cultural_signals=eval_data.get("cultural_signals"),
            red_flags=eval_data.get("red_flags"),
            archetype=eval_data.get("archetype", "Unknown"),
            domain=eval_data.get("domain", ""),
            seniority=eval_data.get("seniority", ""),
            remote_policy=eval_data.get("remote_policy", ""),
            legitimacy=eval_data.get("legitimacy", "Proceed with Caution"),
            reasoning=eval_data.get("reasoning", ""),
            matching_skills=json.dumps(eval_data.get("matching_skills", [])),
            skill_gaps=json.dumps(eval_data.get("skill_gaps", [])),
            gap_analysis=eval_data.get("gap_analysis", ""),
            personalization_plan=eval_data.get("personalization_plan", ""),
            interview_prep=eval_data.get("interview_prep", ""),
        )
        mark_evaluated(job_id)
        logger.info(
            "On-demand score saved for job %d — %.1f/5.0 (legitimacy: %s)",
            job_id,
            eval_data["overall_score"],
            eval_data.get("legitimacy"),
        )
    except Exception as e:
        logger.error(
            "score_job_on_demand: DB write failed for job %d: %s", job_id, e,
            exc_info=True,
        )
        result["error"] = f"Score computed but DB write failed: {e}"
        return result

    result["eval_data"] = eval_data
    result["success"] = True
    return result
