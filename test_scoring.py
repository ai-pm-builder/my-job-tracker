import logging
import sys
import json
import database
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

from scorer.job_scorer import score_job

def test_scoring():
    # 1. Check if there are unscored jobs
    unscored = database.get_unscored_jobs()
    long_unscored = [j for j in unscored if len(j.get("description", "")) > 500]
    
    if not long_unscored:
        logger.info("No long unscored jobs found. Inserting a dummy job.")
        # ... (insertion remains same) ...
        long_unscored = [j for j in database.get_unscored_jobs() if len(j.get("description", "")) > 500]

    # 2. Try to score one job
    job = long_unscored[0]
    logger.info(f"Testing scoring for: {job['title']} at {job['company']}")
    
    try:
        eval_data = score_job(
            job_description=job["description"],
            job_title=job["title"],
            company=job["company"]
        )
        
        logger.info("Scoring result:")
        print(json.dumps(eval_data, indent=2))
        
        # 3. Test database insertion
        matching_skills_str = json.dumps(eval_data.get("matching_skills", []))
        skill_gaps_str = json.dumps(eval_data.get("skill_gaps", []))
        
        score_id = database.insert_score(
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
        logger.info(f"Successfully inserted score with ID: {score_id}")
        
    except Exception as e:
        logger.error(f"Scoring test failed: {e}")

if __name__ == "__main__":
    test_scoring()
