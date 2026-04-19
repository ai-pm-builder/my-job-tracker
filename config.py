"""
Central configuration for the Automated Senior PM Job Search system.
All search parameters, thresholds, and paths are managed here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────── Paths ────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output" / "resumes"
RESUME_PATH = BASE_DIR / "cv" / "Asif-Idris-Senior-product-manager-resume.pdf"
DB_PATH = DATA_DIR / "jobs.db"
PROFILE_CACHE_PATH = DATA_DIR / "profile_cache.json"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────── API Keys ────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ──────────────────────────── Search Configuration ────────────────────────────
SEARCH_TERMS = [
    "Senior Product Manager",
    "Lead Product Manager",
    "Principal Product Manager",
    "Group Product Manager",
]

# Google Jobs requires its own search term format
GOOGLE_SEARCH_TERMS = [
    "Senior Product Manager jobs",
    "Lead Product Manager jobs",
    "Principal Product Manager jobs",
]

# Locations to search — India focus + Remote
LOCATIONS = [
    "Bangalore, India",
    "Mumbai, India",
    "Delhi, India",
    "Hyderabad, India",
    "Pune, India",
    "India",
]

# Job board sources for python-jobspy
JOBSPY_SITES = ["indeed", "linkedin", "glassdoor", "google", "naukri"]

# Country setting for Indeed/Glassdoor
COUNTRY_INDEED = "india"

# ──────────────────────────── Scraping Settings ────────────────────────────
HOURS_OLD = 24              # Only fetch jobs posted within last 24 hours
RESULTS_WANTED = 25         # Max results per search term per site
IS_REMOTE = False           # Set to True to filter remote-only jobs
JOB_TYPE = "fulltime"       # fulltime, parttime, contract, internship

# ──────────────────────────── Scoring Settings (Career-Ops Style) ────────────────────────────
# Scale: 1.0 - 5.0 (inspired by github.com/santifer/career-ops)
SCORE_THRESHOLD = 3.5       # Minimum score — "Decent match, apply only if specific reason"
GOOD_MATCH_THRESHOLD = 4.0  # Minimum score for "Good Match"
STRONG_MATCH_THRESHOLD = 4.5  # Minimum score for "Strong Match"

# Scoring weights (must sum to 1.0)
SCORING_WEIGHTS = {
    "cv_match": 0.35,            # Skills, experience, proof points alignment
    "north_star_alignment": 0.25, # How well role fits target archetypes / career goals
    "compensation": 0.15,        # Salary vs market (5=top quartile, 1=well below)
    "cultural_signals": 0.15,    # Company culture, growth, stability, remote policy
    "red_flags": 0.10,           # Blockers & warnings (inverted: 5=no flags, 1=many)
}

# Score interpretation labels
SCORE_LABELS = {
    4.5: "🟢 Strong Match — Apply immediately",
    4.0: "🔵 Good Match — Worth applying",
    3.5: "🟡 Decent — Apply only with specific reason",
    0.0: "🔴 Weak — Recommend against applying",
}

# Posting Legitimacy tiers
LEGITIMACY_TIERS = ["High Confidence", "Proceed with Caution", "Suspicious"]

# ──────────────────────────── Logging ────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
