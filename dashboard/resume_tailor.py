"""
Resume Tailoring Engine — career-ops style.

Reads the candidate master profile from data/profile_cache.json (user-editable),
loads contact info from profile.yml, then calls Gemini 2.5 Flash to produce a
fully tailored CV for a specific job posting.

First-run behaviour:
  If profile_cache.json does not exist, the module auto-extracts a comprehensive
  structured profile from the resume PDF and saves it. After that the user can
  edit the JSON directly to enrich their master profile.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import yaml
import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

# ── project root on sys.path so we can import config & database ──────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Pydantic schemas for structured LLM output
# ══════════════════════════════════════════════════════════════════════

class ExperienceBullet(BaseModel):
    text: str = Field(description="Single achievement bullet, keyword-injected but truthful")


class ExperienceEntry(BaseModel):
    job_title: str
    company: str
    location: str = ""
    start_date: str
    end_date: str  # "Present" if current
    bullets: list[ExperienceBullet] = Field(
        description="Top 4-6 bullets reordered by JD relevance, keywords injected naturally"
    )


class ProjectEntry(BaseModel):
    name: str
    tech_stack: str = Field(description="Comma-separated technologies used")
    description: str = Field(description="1-2 sentence impact description")


class EducationEntry(BaseModel):
    degree: str
    institution: str
    location: str = ""
    year: str


class TailoredResume(BaseModel):
    """
    Full tailored resume content ready to inject into the HTML template.
    All content is derived from real experience — LLM never invents skills.
    """
    # Career-ops pipeline outputs
    jd_keywords: list[str] = Field(description="15-20 keywords extracted from the JD")
    keyword_coverage_pct: float = Field(description="Percentage of JD keywords covered by tailored resume (0-100)")

    # Rewritten sections
    professional_summary: str = Field(
        description="3-4 sentence summary injecting top 5 JD keywords, keyword-dense"
    )
    core_competencies: list[str] = Field(
        description="6-8 keyword phrases from JD mapped to real candidate skills"
    )
    work_experience: list[ExperienceEntry] = Field(
        description="Full work history with bullets reordered by JD relevance"
    )
    projects: list[ProjectEntry] = Field(
        description="Top 3-4 projects most relevant to this role"
    )
    education: list[EducationEntry]
    certifications: list[str] = Field(
        description="List of certifications, most JD-relevant first"
    )
    skills: dict[str, list[str]] = Field(
        description="Skills grouped by category, e.g. {'Product Management': [...], 'AI/ML': [...]}"
    )


# ══════════════════════════════════════════════════════════════════════
# Profile helpers
# ══════════════════════════════════════════════════════════════════════

def load_profile_yml() -> dict:
    """Load candidate identity & contact info from profile.yml."""
    yml_path = config.PROFILE_YML_PATH
    if not yml_path.exists():
        logger.warning("profile.yml not found at %s — using defaults.", yml_path)
        return {
            "name": "Candidate",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "linkedin_display": "",
            "portfolio_url": "",
            "portfolio_display": "",
            "resume_pdf": str(config.RESUME_PATH),
            "profile_cache": str(config.PROFILE_CACHE_PATH),
        }
    with open(yml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from a PDF using PyMuPDF."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")
    doc = fitz.open(str(pdf_path))
    return "\n".join(page.get_text() for page in doc).strip()


class ComprehensiveProfile(BaseModel):
    """Rich schema for the one-time profile extraction from the resume PDF."""
    name: str
    skills: list[str] = Field(description="All technical and soft skills mentioned")
    experience_summary: str = Field(description="2-3 sentence career narrative")
    proof_points: list[str] = Field(description="All quantified achievements e.g. 'Reduced latency 40%'")
    target_archetypes: list[str] = Field(description="Matching AI/Tech archetypes for this candidate")
    work_experience: list[ExperienceEntry] = Field(
        description="Full work history extracted from PDF, newest first"
    )
    projects: list[ProjectEntry] = Field(description="Side projects, open-source, or portfolio pieces")
    education: list[EducationEntry]
    certifications: list[str]
    skills_by_category: dict[str, list[str]] = Field(
        description="Skills grouped by category"
    )


_EXTRACTION_PROMPT = """\
You are an expert technical recruiter extracting a comprehensive structured profile from a resume.
Extract EVERYTHING — do not summarise or drop information.
Return a JSON matching the required schema exactly.

CRITICAL RULES:
1. Extract all work experience with EXACT company names, job titles, and dates.
2. For each role, extract ALL bullet points / achievement statements verbatim.
3. Extract all projects, education, and certifications.
4. Identify all technical and soft skills explicitly mentioned.
5. Identify quantified proof points (metrics, percentages, numbers).
6. NEVER invent or infer content not present in the resume.

Resume text:
```
{resume_text}
```
"""


def bootstrap_profile_cache(profile_yml: dict) -> dict:
    """
    First-run: extract comprehensive profile from PDF → save to profile_cache.json.
    Returns the profile dict.
    """
    resume_pdf_path = ROOT / profile_yml.get("resume_pdf", str(config.RESUME_PATH))
    cache_path = ROOT / profile_yml.get("profile_cache", str(config.PROFILE_CACHE_PATH))

    logger.info("Bootstrapping master profile from PDF: %s", resume_pdf_path)
    raw_text = _extract_pdf_text(resume_pdf_path)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_retries=2,
    )
    structured_llm = llm.with_structured_output(ComprehensiveProfile)

    try:
        response = structured_llm.invoke(
            _EXTRACTION_PROMPT.format(resume_text=raw_text)
        )
        profile_data = response.model_dump()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        logger.info(
            "Master profile saved to %s — you can now edit this JSON to enrich your profile.",
            cache_path,
        )
        return profile_data
    except Exception as e:
        logger.error("Profile extraction failed: %s", e)
        raise


def load_master_profile(profile_yml: dict) -> dict:
    """
    Load master profile from cache JSON. Auto-bootstrap from PDF if not present.
    """
    cache_path = ROOT / profile_yml.get("profile_cache", str(config.PROFILE_CACHE_PATH))
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
                logger.debug("Loaded master profile from cache (%s)", cache_path)
                return profile
        except json.JSONDecodeError:
            logger.warning("profile_cache.json is corrupted — re-extracting from PDF.")
    return bootstrap_profile_cache(profile_yml)


# ══════════════════════════════════════════════════════════════════════
# Tailoring prompt
# ══════════════════════════════════════════════════════════════════════

_TAILORING_PROMPT = """\
You are a senior career coach and expert resume writer applying the career-ops methodology.
Your task: tailor the candidate's resume for this specific job, following every rule below.

═══ CANDIDATE MASTER PROFILE ═══
{master_profile}

═══ JOB DESCRIPTION ═══
Title: {job_title}
Company: {company}
{job_description}

═══ TAILORING RULES (MANDATORY) ═══

1. KEYWORD EXTRACTION
   - Extract 15-20 high-value keywords/phrases from the JD (skills, technologies, methodologies, domain terms).
   - These are the terms ATS systems scan for.

2. PROFESSIONAL SUMMARY (3-4 sentences)
   - Inject the TOP 5 most critical JD keywords naturally.
   - Lead with seniority + domain + impact style.
   - Never start with "I".

3. CORE COMPETENCIES (6-8 items)
   - Each item is a keyword phrase directly from the JD, mapped to a real candidate skill.
   - Format: short (2-4 words), ATS-scannable phrases.

4. WORK EXPERIENCE
   - Keep ALL roles from the master profile. Do NOT drop any employer.
   - For each role, REORDER bullets so the most JD-relevant achievements come FIRST.
   - INJECT JD keywords naturally into existing bullet text — only reformulate, NEVER invent.
   - Example: JD says "stakeholder management" and CV says "collaborated with team" → change to
     "stakeholder management across engineering, product, and operations teams"
   - Preserve all metrics and numbers exactly.

5. PROJECTS
   - Select the 3-4 projects most relevant to this role.
   - Same keyword injection rules apply.

6. SKILLS
   - Group by category. Put categories most relevant to JD first.

7. GOLDEN RULE: NEVER add skills, technologies, or achievements the candidate does not have.
   Only reformulate real experience using the JD's vocabulary.

8. keyword_coverage_pct: calculate what % of extracted JD keywords appear in your tailored resume.
   Target ≥ 70%.

Return ONLY the JSON matching the TailoredResume schema. Ensure valid JSON.
"""


# ══════════════════════════════════════════════════════════════════════
# Main public function
# ══════════════════════════════════════════════════════════════════════

def tailor_resume(
    job_title: str,
    company: str,
    job_description: str,
) -> TailoredResume:
    """
    Generate a tailored resume for the given job.

    Steps:
      1. Load profile.yml (contact info)
      2. Load / bootstrap master profile JSON
      3. Call Gemini 2.5 Flash with tailoring prompt
      4. Return structured TailoredResume

    Returns:
        TailoredResume pydantic model ready for pdf_generator.
    """
    profile_yml = load_profile_yml()
    master_profile = load_master_profile(profile_yml)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3,
        max_retries=2,
    )
    structured_llm = llm.with_structured_output(TailoredResume)

    prompt = _TAILORING_PROMPT.format(
        master_profile=json.dumps(master_profile, indent=2, ensure_ascii=False),
        job_title=job_title,
        company=company,
        job_description=job_description,
    )

    logger.info("Calling Gemini to tailor resume for '%s' at %s...", job_title, company)
    tailored: TailoredResume = structured_llm.invoke(prompt)
    logger.info(
        "Resume tailored — keyword coverage: %.0f%%, competencies: %d",
        tailored.keyword_coverage_pct,
        len(tailored.core_competencies),
    )
    return tailored
