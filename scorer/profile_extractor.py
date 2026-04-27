"""
Extracts a structured candidate profile from a resume PDF.
Caches the structured JSON to avoid hitting LLM unnecessarily on every run.
"""

import json
import logging
import fitz  # PyMuPDF
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

import config
from scorer.prompts import PROFILE_PROMPT

logger = logging.getLogger(__name__)

# ──────────────────────────── Schema ────────────────────────────

class CandidateProfile(BaseModel):
    skills: list[str] = Field(description="Top technical and soft skills")
    experience_summary: str = Field(description="Summary of professional experience")
    proof_points: list[str] = Field(description="List of solid achievements with metrics (e.g. 'Reduced latency by 40%')")
    target_archetypes: list[str] = Field(description="Which archetypes best describe this profile")

# ──────────────────────────── Extraction ────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract raw text from a PDF file."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Resume PDF not found at {pdf_path}")
    
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()


def get_structured_profile() -> dict:
    """
    Get the structured profile from cache, or generate it via Gemini if not cached.
    """
    cache_path = Path(config.PROFILE_CACHE_PATH)
    
    # Return cache if exists
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                logger.debug("Loaded existing structured profile from cache.")
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Cache file is corrupted. Re-generating...")
            
    # Generate new profile
    logger.info("Extracting structured candidate profile from PDF (first run)...")
    raw_text = extract_text_from_pdf(config.RESUME_PATH)
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-lite",
        temperature=0.1,
        # Use structured output for guaranteed JSON mapping
    )
    structured_llm = llm.with_structured_output(CandidateProfile)
    
    prompt = PROFILE_PROMPT.format(resume_text=raw_text)
    
    try:
        response = structured_llm.invoke(prompt)
        profile_data = response.model_dump()
        
        # Save to cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=4)
        
        logger.info("Successfully extracted and cached candidate profile.")
        return profile_data
    except Exception as e:
        logger.error(f"Failed to extract structured profile: {e}")
        # Return fallback generic profile so pipeline can continue
        return {
            "skills": ["Product Management"],
            "experience_summary": "Extracted via raw text: " + raw_text[:500] + "...",
            "proof_points": [],
            "target_archetypes": ["Technical AI Product Manager", "Generalist Product Manager"]
        }
