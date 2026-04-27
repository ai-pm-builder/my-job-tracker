"""
Job Tracker Dashboard — Streamlit app (Module 3).

Run with:
    streamlit run dashboard/app.py

Features:
  • Stats bar: total jobs, scored, avg score, tailored resumes
  • Sidebar filters: Job Mode, Posted Time, Score range, free-text search
  • Jobs table with expandable detail panels
  • "🎯 Create Tailored Resume" button per row → Gemini tailoring → PDF download
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── project root on sys.path ─────────────────────────────────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database
import config

# ── logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Page config
# ══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Job Tracker Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Import Google Fonts */
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:ital,wght@0,400;0,500;0,700&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  /* ── Page title ── */
  h1 { font-family: 'Space Grotesk', sans-serif !important; }
  h2, h3 { font-family: 'Space Grotesk', sans-serif !important; }

  /* ── Metric cards ── */
  [data-testid="metric-container"] {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
    color: #f1f5f9;
  }
  [data-testid="metric-container"] label {
    color: #94a3b8 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem !important;
    color: #f1f5f9 !important;
    font-weight: 700;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #0f172a;
    border-right: 1px solid #1e293b;
  }
  [data-testid="stSidebar"] * { color: #cbd5e1 !important; }
  [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #38bdf8 !important;
  }
  [data-testid="stSidebar"] .stSlider > div > div { background: #38bdf8 !important; }

  /* ── Score badge colours ── */
  .badge-strong { background:#166534; color:#bbf7d0; border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
  .badge-good   { background:#1e40af; color:#bfdbfe; border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
  .badge-decent { background:#713f12; color:#fef9c3; border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
  .badge-weak   { background:#7f1d1d; color:#fecaca; border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }

  /* ── Legitimacy badge ── */
  .leg-high    { color:#4ade80; font-weight:600; }
  .leg-caution { color:#facc15; font-weight:600; }
  .leg-suspect { color:#f87171; font-weight:600; }

  /* ── Job card ── */
  .job-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
  }
  .job-card:hover { border-color: #38bdf8; }
  .job-title-text {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: #f1f5f9;
  }
  .job-company-text { color: #a78bfa; font-weight: 500; }
  .job-meta { color: #64748b; font-size: 0.82rem; }

  /* ── Detail panel ── */
  .detail-panel {
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 16px;
    margin-top: 8px;
  }
  .detail-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #38bdf8;
    margin-bottom: 4px;
  }

  /* ── Buttons ── */
  .stButton button {
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
  }

  /* ── Download button ── */
  .stDownloadButton button {
    background: linear-gradient(135deg, hsl(187,74%,32%), hsl(270,70%,45%)) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
  }

  /* ── Divider ── */
  hr { border-color: #1e293b !important; }

  /* Main background */
  .main { background: #0a0f1e; }
  .block-container { background: #0a0f1e; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════

def score_badge(score) -> str:
    """Return an HTML badge for a score value."""
    if score is None:
        return '<span style="color:#64748b">—</span>'
    if score >= 4.5:
        return f'<span class="badge-strong">🟢 {score:.1f}</span>'
    if score >= 4.0:
        return f'<span class="badge-good">🔵 {score:.1f}</span>'
    if score >= 3.5:
        return f'<span class="badge-decent">🟡 {score:.1f}</span>'
    return f'<span class="badge-weak">🔴 {score:.1f}</span>'


def legitimacy_badge(legitimacy: str) -> str:
    if not legitimacy:
        return "—"
    if "High" in legitimacy:
        return f'<span class="leg-high">✓ {legitimacy}</span>'
    if "Caution" in legitimacy:
        return f'<span class="leg-caution">⚠ {legitimacy}</span>'
    return f'<span class="leg-suspect">✗ {legitimacy}</span>'


def format_date(date_str: str) -> str:
    """Format a date string to a friendly short form."""
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(date_str)[:10]


def parse_json_list(s) -> list:
    """Safely parse a JSON string or return empty list."""
    if not s:
        return []
    if isinstance(s, list):
        return s
    try:
        val = json.loads(s)
        return val if isinstance(val, list) else []
    except Exception:
        return [s] if s else []


def mode_icon(mode: str) -> str:
    if not mode:
        return "🏢"
    m = mode.lower()
    if "remote" in m:
        return "🏠 Remote"
    if "hybrid" in m:
        return "🔀 Hybrid"
    return "🏢 Onsite"


# ══════════════════════════════════════════════════════════════════════
# Resume generation (cached per job_id in session state)
# ══════════════════════════════════════════════════════════════════════

def generate_tailored_resume(job: dict) -> Path:
    """Run the full tailoring pipeline for a job. Returns the PDF path."""
    from dashboard.resume_tailor import tailor_resume
    from dashboard.pdf_generator import generate_pdf

    with st.spinner(f"🤖 Gemini is tailoring your resume for **{job['title']}** at **{job['company']}**…"):
        tailored = tailor_resume(
            job_title=job["title"],
            company=job["company"] or "Unknown",
            job_description=job.get("description", ""),
        )

    with st.spinner("📄 Rendering PDF with Playwright…"):
        pdf_path = generate_pdf(
            tailored=tailored,
            company=job["company"] or "Unknown",
            job_id=job["id"],
            tailored_summary=tailored.professional_summary[:200],
        )

    return pdf_path


# ══════════════════════════════════════════════════════════════════════
# Sidebar filters
# ══════════════════════════════════════════════════════════════════════

def render_sidebar() -> dict:
    """Render sidebar filters and return the current filter state."""
    with st.sidebar:
        st.markdown("## 🎯 Job Tracker")
        st.markdown("---")

        # ── Search ────────────────────────────────────────────────
        st.markdown("### 🔍 Search")
        search = st.text_input(
            "Title or company",
            placeholder="e.g. Product Manager, Google…",
            label_visibility="collapsed",
        )

        st.markdown("### 🌐 Job Mode")
        mode_options = ["Remote", "Hybrid", "Onsite"]
        selected_modes = st.multiselect(
            "Job mode",
            options=mode_options,
            default=[],
            label_visibility="collapsed",
        )

        st.markdown("### 📅 Posted Time")
        time_option = st.radio(
            "Posted within",
            options=["All", "24 hours", "3 days", "7 days", "15 days"],
            index=0,
            label_visibility="collapsed",
        )
        days_map = {"All": None, "24 hours": 1, "3 days": 3, "7 days": 7, "15 days": 15}
        days = days_map[time_option]

        st.markdown("### ⭐ Score Range")
        score_range = st.slider(
            "Score range",
            min_value=1.0,
            max_value=5.0,
            value=(1.0, 5.0),
            step=0.5,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown(
            '<div style="color:#475569;font-size:0.75rem;text-align:center;">'
            'Powered by Gemini 2.5 Flash · career-ops style</div>',
            unsafe_allow_html=True,
        )

    return {
        "search": search.strip() if search else None,
        "modes": selected_modes if selected_modes else None,
        "days": days,
        "min_score": score_range[0],
        "max_score": score_range[1],
    }


# ══════════════════════════════════════════════════════════════════════
# Stats bar
# ══════════════════════════════════════════════════════════════════════

def render_stats(stats: dict):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Jobs", stats.get("total_jobs", 0))
    col2.metric("Scored", stats.get("scored_jobs", 0))
    col3.metric("Avg Score", f"{stats.get('avg_score', 0):.1f} / 5.0")
    col4.metric("Strong Matches ≥4.5", stats.get("high_match", 0))
    col5.metric("Tailored Resumes", stats.get("tailored_resumes", 0))


# ══════════════════════════════════════════════════════════════════════
# Job detail panel
# ══════════════════════════════════════════════════════════════════════

def render_job_detail(job: dict, idx: int):
    """Render the expandable detail panel for a single job row."""
    with st.expander(f"📋 Details — {job.get('title', '')} @ {job.get('company', '')}", expanded=False):
        col_left, col_right = st.columns([3, 2])

        with col_left:
            # ── Role TLDR ──────────────────────────────────────────
            if job.get("reasoning"):
                st.markdown('<div class="detail-label">Evaluation Summary</div>', unsafe_allow_html=True)
                st.caption(job["reasoning"][:500] + ("…" if len(str(job["reasoning"])) > 500 else ""))

            # ── Matching skills ────────────────────────────────────
            matching = parse_json_list(job.get("matching_skills"))
            if matching:
                st.markdown('<div class="detail-label">✅ Matching Skills</div>', unsafe_allow_html=True)
                st.markdown(" · ".join(f"`{s}`" for s in matching))

            # ── Skill gaps ─────────────────────────────────────────
            gaps = parse_json_list(job.get("skill_gaps"))
            if gaps:
                st.markdown('<div class="detail-label">⚠️ Skill Gaps</div>', unsafe_allow_html=True)
                st.markdown(" · ".join(f"`{s}`" for s in gaps))

            # ── Gap analysis ───────────────────────────────────────
            if job.get("gap_analysis"):
                st.markdown('<div class="detail-label">🔧 Gap Analysis</div>', unsafe_allow_html=True)
                st.caption(job["gap_analysis"])

        with col_right:
            # ── Score dimensions ───────────────────────────────────
            st.markdown('<div class="detail-label">📊 Score Breakdown</div>', unsafe_allow_html=True)
            dims = [
                ("CV Match", job.get("cv_match")),
                ("North Star", job.get("north_star_alignment")),
                ("Compensation", job.get("compensation")),
                ("Culture", job.get("cultural_signals")),
                ("Red Flags", job.get("red_flags")),
            ]
            for label, val in dims:
                if val is not None:
                    st.progress(
                        int((val / 5.0) * 100),
                        text=f"{label}: {val:.1f}",
                    )

            # ── Personalization plan ───────────────────────────────
            if job.get("personalization_plan"):
                st.markdown('<div class="detail-label">✍️ Personalization Plan</div>', unsafe_allow_html=True)
                st.caption(job["personalization_plan"])

        st.markdown("---")

        # ── Interview prep ─────────────────────────────────────────
        if job.get("interview_prep"):
            st.markdown('<div class="detail-label">🎤 Interview Prep (STAR Stories)</div>', unsafe_allow_html=True)
            st.info(job["interview_prep"])

        # ── Job description ────────────────────────────────────────
        with st.expander("📄 Full Job Description", expanded=False):
            st.text(job.get("description", "No description available.")[:3000])

        # ── Apply link ─────────────────────────────────────────────
        if job.get("job_url"):
            st.link_button("🔗 Apply / View Posting", job["job_url"])


# ══════════════════════════════════════════════════════════════════════
# Main job table
# ══════════════════════════════════════════════════════════════════════

def render_jobs_table(jobs: list[dict]):
    """Render the full jobs list with per-row action buttons."""
    if not jobs:
        st.info("No jobs match your current filters. Try broadening the search.")
        return

    st.markdown(f"**{len(jobs)} jobs found**")
    st.markdown("---")

    # ── Session state for generated resumes ───────────────────────
    if "generated_pdfs" not in st.session_state:
        st.session_state.generated_pdfs = {}

    for idx, job in enumerate(jobs):
        job_id = job["id"]
        score = job.get("overall_score")
        has_resume = bool(job.get("has_resume"))
        resume_path = job.get("resume_path")

        # ── Job card header ────────────────────────────────────────
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 1.2, 1, 1.5, 1.8])

        with c1:
            st.markdown(
                f'<span class="job-title-text">{job.get("title", "—")}</span><br/>'
                f'<span class="job-company-text">{job.get("company", "—")}</span>',
                unsafe_allow_html=True,
            )

        with c2:
            loc = job.get("location") or "—"
            mode = mode_icon(job.get("remote_policy") or ("Remote" if job.get("is_remote") else ""))
            st.markdown(
                f'<span class="job-meta">📍 {loc}</span><br/>'
                f'<span class="job-meta">{mode}</span>',
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown(score_badge(score), unsafe_allow_html=True)

        with c4:
            st.markdown(
                legitimacy_badge(job.get("legitimacy")),
                unsafe_allow_html=True,
            )

        with c5:
            posted = job.get("date_posted") or job.get("date_scraped")
            st.markdown(
                f'<span class="job-meta">{format_date(posted)}</span>',
                unsafe_allow_html=True,
            )

        with c6:
            # ── Resume button / download ───────────────────────────
            btn_key = f"resume_btn_{job_id}_{idx}"
            dl_key = f"dl_{job_id}_{idx}"

            # If already generated this session
            if job_id in st.session_state.generated_pdfs:
                pdf_path = Path(st.session_state.generated_pdfs[job_id])
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download PDF",
                            data=f.read(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            key=dl_key,
                        )
                else:
                    st.error("PDF missing")

            elif has_resume and resume_path and Path(resume_path).exists():
                # Resume already exists in DB from a previous session
                with open(resume_path, "rb") as f:
                    st.download_button(
                        label="✅ Resume Ready",
                        data=f.read(),
                        file_name=Path(resume_path).name,
                        mime="application/pdf",
                        key=dl_key,
                    )
            else:
                if st.button("🎯 Tailor Resume", key=btn_key):
                    try:
                        pdf_path = generate_tailored_resume(job)
                        st.session_state.generated_pdfs[job_id] = str(pdf_path)
                        st.success(f"PDF created: `{pdf_path.name}`")
                        st.rerun()
                    except Exception as e:
                        logger.error("Resume generation failed for job %d: %s", job_id, e, exc_info=True)
                        st.error(f"Generation failed: {e}")

        # ── Expandable detail panel ────────────────────────────────
        render_job_detail(job, idx)
        st.markdown('<hr style="margin: 6px 0; border-color: #1e293b;">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    # ── Title ──────────────────────────────────────────────────────
    st.markdown("""
    <h1 style="
      font-family: 'Space Grotesk', sans-serif;
      background: linear-gradient(90deg, hsl(187,74%,52%), hsl(270,70%,65%));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 4px;
    ">🎯 Job Tracker Dashboard</h1>
    <p style="color:#64748b; margin-bottom: 20px; font-size:0.9rem;">
      AI-scored job listings · career-ops resume tailoring · ATS-optimized PDFs
    </p>
    """, unsafe_allow_html=True)

    # ── Sidebar filters ────────────────────────────────────────────
    filters = render_sidebar()

    # ── Stats bar ──────────────────────────────────────────────────
    stats = database.get_job_stats()
    render_stats(stats)
    st.markdown("---")

    # ── Fetch filtered jobs ────────────────────────────────────────
    jobs = database.get_filtered_jobs(
        modes=filters["modes"],
        days=filters["days"],
        min_score=filters["min_score"],
        max_score=filters["max_score"],
        search=filters["search"],
    )

    # ── Table ──────────────────────────────────────────────────────
    # Column headers
    h1, h2, h3, h4, h5, h6 = st.columns([3, 2, 1.2, 1, 1.5, 1.8])
    h1.markdown("**Job / Company**")
    h2.markdown("**Location / Mode**")
    h3.markdown("**Score**")
    h4.markdown("**Trust**")
    h5.markdown("**Posted**")
    h6.markdown("**Resume**")
    st.markdown('<hr style="margin: 4px 0; border-color: #334155;">', unsafe_allow_html=True)

    render_jobs_table(jobs)


if __name__ == "__main__":
    main()
