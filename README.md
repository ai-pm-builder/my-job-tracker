# 🎯 Automated Senior PM Job Tracker

An end-to-end automated pipeline for **Senior Product Manager job search** — scraping, AI-scoring, and resume tailoring, all from a single command.

Inspired by the multi-dimensional scoring methodology from [career-ops](https://github.com/santifer/career-ops), but **fully independent** — no proprietary CLI tools, no Claude Code, no platform lock-in. Just Python, the Gemini API, and a local SQLite database.

---

## ✨ Features

- **Multi-source job scraping** — LinkedIn, Indeed, Glassdoor, Google Jobs, Naukri, Greenhouse, and Lever ATS boards
- **AI-powered job scoring** — Multi-dimensional evaluation (1.0–5.0 scale) via Gemini 2.5 Flash with structured output
- **Posting legitimacy check** — flags ghost postings and suspicious listings before you apply
- **Resume-aware matching** — extracts your skills and proof points from your CV PDF, cached locally to avoid repeated API calls
- **SQLite persistence** — all jobs, scores, and metadata stored locally; deduplication built-in
- **Configurable thresholds** — tune score cutoffs, weights, search terms, and locations in one central `config.py`

---

## 🏗️ Architecture

```
├── main.py                   # Pipeline entry point (Scrape → Score)
├── config.py                 # Central configuration (paths, thresholds, weights)
├── database.py               # SQLite schema, inserts, and queries
│
├── scraper/
│   ├── job_scraper.py        # python-jobspy → LinkedIn, Indeed, Glassdoor, Google, Naukri
│   ├── greenhouse_scraper.py # Direct Greenhouse ATS board scraper
│   ├── lever_scraper.py      # Direct Lever ATS board scraper
│   └── company_list.py       # Target companies for ATS scraping
│
├── scorer/
│   ├── job_scorer.py         # Core scoring engine (Gemini + structured output)
│   ├── profile_extractor.py  # Extracts & caches structured profile from resume PDF
│   └── prompts.py            # LLM prompt templates
│
├── cv/                       # Your resume PDF (gitignored)
├── data/                     # SQLite DB + pipeline logs (gitignored)
├── output/                   # Tailored resumes output (gitignored)
└── run_job_search.bat        # Windows one-click runner
```

---

## 🧠 Scoring System

> Inspired by the career-ops methodology — adapted for standalone use without any external tool dependency.

Each job is scored across **5 weighted dimensions**:

| Dimension | Weight | What it measures |
|---|---|---|
| `cv_match` | 35% | Skill alignment, experience fit, proof points overlap |
| `north_star_alignment` | 25% | Match to target role archetypes and career goals |
| `compensation` | 15% | Salary vs. market (estimated from JD signals) |
| `cultural_signals` | 15% | Company culture, remote policy, stability |
| `red_flags` | 10% | Blockers and warnings (inverted: 5 = no flags) |

### Score Labels

| Score | Label |
|---|---|
| ≥ 4.5 | 🟢 Strong Match — Apply immediately |
| ≥ 4.0 | 🔵 Good Match — Worth applying |
| ≥ 3.5 | 🟡 Decent — Apply only with specific reason |
| < 3.5 | 🔴 Weak — Recommend against applying |

Each evaluation also includes:
- **Legitimacy rating**: `High Confidence`, `Proceed with Caution`, or `Suspicious`
- **Skill gap analysis** with mitigation strategies
- **CV personalization plan** — top 5 changes to maximize ATS match
- **Interview prep** — STAR+R story suggestions mapped to the specific role

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd my-job-tracker
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS / Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

> Get your free API key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### 5. Add your resume

Place your resume PDF inside the `cv/` folder and update the filename in `config.py`:

```python
RESUME_PATH = BASE_DIR / "cv" / "your-resume-filename.pdf"
```

The `cv/` directory is gitignored — your resume will never be committed.

### 6. Configure your search

Edit `config.py` to set your desired:
- `SEARCH_TERMS` — job titles to search
- `LOCATIONS` — cities or regions
- `SCORE_THRESHOLD` — minimum score to flag as a match
- `SCORING_WEIGHTS` — adjust dimension importance to fit your priorities

---

## ▶️ Running the Pipeline

**Windows (one-click):**

```bash
run_job_search.bat
```

**Python directly:**

```bash
python main.py
```

The pipeline will:
1. Scrape all configured sources for new jobs
2. Deduplicate against the local database
3. Score every new job using the Gemini API
4. Log results and store everything in `data/jobs.db`

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `python-jobspy` | Scraping LinkedIn, Indeed, Glassdoor, Google Jobs, Naukri |
| `requests` + `beautifulsoup4` | Greenhouse & Lever ATS scraping |
| `langchain-google-genai` | Gemini API integration via LangChain |
| `pydantic` | Structured output schema validation |
| `pymupdf` | PDF text extraction from resume |
| `pandas` | Data handling for scraped results |
| `python-dotenv` | `.env` file loading |

---

## 🔒 Privacy & Security

- Your resume is stored locally and gitignored
- API keys are loaded from `.env`, never hardcoded
- Job data and logs are stored in `data/` — also gitignored
- The profile extracted from your resume is cached locally in `data/profile_cache.json`

---

## 🗺️ Roadmap

- [x] Module 1 — Multi-source job scraping
- [x] Module 2 — AI-powered multi-dimensional scoring
- [ ] Module 3 — Automated ATS-optimized resume tailoring per job
- [ ] Daily digest delivery (email / Telegram)
- [ ] Web dashboard for browsing scored jobs

---

## 🙏 Credits

Scoring methodology inspired by the [career-ops](https://github.com/santifer/career-ops) framework. This project is an independent reimplementation using open-source Python libraries and the Google Gemini API — no commercial CLI tools or proprietary platforms required.
