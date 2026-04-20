"""
Evaluates a single job opportunity against the candidate's structured profile
using the career-ops A-G block methodology.
"""

import json
import logging
import traceback
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.exceptions import OutputParserException

import config
from scorer.prompts import JOB_EVAL_PROMPT
from scorer.profile_extractor import get_structured_profile

logger = logging.getLogger(__name__)

# ──────────────────────────── Structured Output Schema ────────────────────────────

class JobEvaluation(BaseModel):
    # Block A - Role Summary
    archetype: str = Field(description="Detected AI/Tech archetype")
    domain: str = Field(description="Company/role domain (e.g., Enterprise, SaaS, FinTech)")
    seniority: str = Field(description="Role seniority level")
    remote_policy: str = Field(description="Remote, Hybrid, or Onsite")
    role_tldr: str = Field(description="1-sentence summary of the role")

    # Dimensional Scores (1.0 - 5.0)
    cv_match: float = Field(ge=1.0, le=5.0)
    north_star_alignment: float = Field(ge=1.0, le=5.0)
    compensation: float = Field(ge=1.0, le=5.0)
    cultural_signals: float = Field(ge=1.0, le=5.0)
    red_flags: float = Field(ge=1.0, le=5.0)
    
    # Global
    overall_score: float = Field(ge=1.0, le=5.0, description="Weighted average based on config weights")

    # Block B & Strategy Details
    matching_skills: list[str] = Field(description="Exact candidate skills found in JD")
    skill_gaps: list[str] = Field(description="JD requirements candidate lacks")
    gap_analysis: str = Field(description="Mitigation strategies for the identified gaps")
    
    # Block E & F
    personalization_plan: str = Field(description="Top 5 CV changes to maximize match")
    interview_prep: str = Field(description="2-3 STAR+R stories mapped to this role")

    # Block G
    legitimacy: str = Field(description="High Confidence, Proceed with Caution, or Suspicious")
    legitimacy_signals: str = Field(description="Why it received this legitimacy rating")

    # Overall Narrative
    reasoning: str = Field(description="Detailed evaluation narrative tying it all together")

# ──────────────────────────── Scoring Engine ────────────────────────────

def score_job(job_description: str, job_title: str, company: str) -> dict:
    """
    Score a job using Gemini 2.5 Flash.
    Returns a dictionary matching the JobEvaluation schema.
    """
    if not job_description or len(job_description.strip()) < 50:
        logger.warning(f"Job description too short for '{job_title}' at {company}. Skipping full evaluation.")
        return get_fallback_evaluation()

    # Get cached profile
    profile = get_structured_profile()

    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2, # Low temp for analytical consistency
        max_retries=2
    )
    structured_llm = llm.with_structured_output(JobEvaluation)
    
    prompt = JOB_EVAL_PROMPT.format(
        candidate_profile=json.dumps(profile, indent=2),
        job_description=f"Title: {job_title}\nCompany: {company}\n\n{job_description}"
    )

    try:
        logger.debug(f"Calling Gemini to evaluate '{job_title}' at {company}...")
        evaluation: JobEvaluation = structured_llm.invoke(prompt)
        return evaluation.model_dump()
        
    except OutputParserException as e:
        logger.error(f"Structured output error for '{job_title}': {e}")
        return get_fallback_evaluation()
    except Exception as e:
        logger.error(f"Scoring error for '{job_title}': {e}")
        logger.debug(traceback.format_exc())
        return get_fallback_evaluation()


def get_fallback_evaluation() -> dict:
    """Return a neutral fallback if scoring completely fails."""
    return {
        "archetype": "Unknown",
        "domain": "Unknown",
        "seniority": "Unknown",
        "remote_policy": "Unknown",
        "role_tldr": "Failed to evaluate JD properly.",
        "cv_match": 3.0,
        "north_star_alignment": 3.0,
        "compensation": 3.0,
        "cultural_signals": 3.0,
        "red_flags": 3.0,
        "overall_score": 3.0,
        "matching_skills": [],
        "skill_gaps": ["Evaluation Failed"],
        "gap_analysis": "N/A",
        "personalization_plan": "N/A",
        "interview_prep": "N/A",
        "legitimacy": "Proceed with Caution",
        "legitimacy_signals": "Automated text extraction or API failure.",
        "reasoning": "The AI scoring pipeline encountered an error reading or processing this job description."
    }
