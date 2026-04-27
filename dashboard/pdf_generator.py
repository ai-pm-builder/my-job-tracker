"""
PDF Generator — HTML → PDF via Playwright (Python binding).

Python equivalent of career-ops' generate-pdf.mjs.
Fills the cv-template.html with TailoredResume content,
then renders it to a PDF using headless Chromium.
"""

import html as html_lib
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── project root on sys.path ────────────────────────────────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
import database
from dashboard.resume_tailor import TailoredResume, load_profile_yml

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# HTML rendering helpers
# ══════════════════════════════════════════════════════════════════════

def _e(text: str) -> str:
    """HTML-escape a string for safe injection into template."""
    return html_lib.escape(str(text or ""))


def _render_competencies(tags: list[str]) -> str:
    return "\n".join(
        f'<span class="competency-tag">{_e(t)}</span>' for t in tags
    )


def _render_experience(experience: list) -> str:
    blocks = []
    for entry in experience:
        # Support both Pydantic objects and plain dicts
        if hasattr(entry, "model_dump"):
            e = entry.model_dump()
        else:
            e = entry

        bullets_html = "\n".join(
            f"<li>{_e(b['text'] if isinstance(b, dict) else b.text)}</li>"
            for b in e.get("bullets", [])
        )

        location_html = f'<span class="job-location"> · {_e(e.get("location", ""))}</span>' if e.get("location") else ""

        blocks.append(f"""
<div class="job-entry">
  <div class="job-header">
    <span class="job-title">{_e(e.get("job_title", ""))}</span>
    <span class="job-dates">{_e(e.get("start_date", ""))} – {_e(e.get("end_date", ""))}</span>
  </div>
  <div class="job-company">{_e(e.get("company", ""))}{location_html}</div>
  <ul class="job-bullets">
    {bullets_html}
  </ul>
</div>""")
    return "\n".join(blocks)


def _render_projects(projects: list) -> str:
    if not projects:
        return ""
    blocks = []
    for proj in projects:
        if hasattr(proj, "model_dump"):
            p = proj.model_dump()
        else:
            p = proj
        tech_html = f'<span class="project-tech">{_e(p.get("tech_stack", ""))}</span>' if p.get("tech_stack") else ""
        blocks.append(f"""
<div class="project-entry">
  <div class="project-header">
    <span class="project-name">{_e(p.get("name", ""))}</span>
    {tech_html}
  </div>
  <p class="project-desc">{_e(p.get("description", ""))}</p>
</div>""")
    return "\n".join(blocks)


def _render_education(education: list) -> str:
    blocks = []
    for edu in education:
        if hasattr(edu, "model_dump"):
            e = edu.model_dump()
        else:
            e = edu
        year_html = f'<span class="edu-dates">{_e(e.get("year", ""))}</span>' if e.get("year") else ""
        loc_html = f' · {_e(e.get("location", ""))}' if e.get("location") else ""
        blocks.append(f"""
<div class="edu-entry">
  <div class="edu-header">
    <span class="edu-degree">{_e(e.get("degree", ""))}</span>
    {year_html}
  </div>
  <div class="edu-institution">{_e(e.get("institution", ""))}{loc_html}</div>
</div>""")
    return "\n".join(blocks)


def _render_certifications(certs: list[str]) -> str:
    if not certs:
        return ""
    items = "\n".join(f"<li>{_e(c)}</li>" for c in certs)
    return f'<ul class="cert-list">\n{items}\n</ul>'


def _render_skills(skills: dict[str, list[str]]) -> str:
    rows = []
    for category, items in skills.items():
        rows.append(
            f'<div><span class="skill-category">{_e(category)}:</span> '
            f'<span class="skill-items">{_e(", ".join(items))}</span></div>'
        )
    return "\n".join(rows)


# ══════════════════════════════════════════════════════════════════════
# Template filling
# ══════════════════════════════════════════════════════════════════════

def fill_template(tailored: TailoredResume, profile: dict) -> str:
    """
    Fill the cv-template.html with tailored content and candidate contact info.
    Returns complete HTML string ready for Playwright.
    """
    template_path = config.CV_TEMPLATE_PATH
    if not template_path.exists():
        raise FileNotFoundError(f"CV template not found at {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = f.read()

    # ── Contact info from profile.yml ──────────────────────────────
    name = profile.get("name", "Candidate")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    location = profile.get("location", "")
    linkedin_url = profile.get("linkedin_url", "")
    linkedin_display = profile.get("linkedin_display", linkedin_url)
    portfolio_url = profile.get("portfolio_url", "")
    portfolio_display = profile.get("portfolio_display", portfolio_url)

    # Optional phone span
    phone_html = (
        f'<span class="separator">·</span><span>{_e(phone)}</span>'
        if phone else ""
    )

    # Optional portfolio span
    portfolio_html = (
        f'<span class="separator">·</span>'
        f'<span><a href="{_e(portfolio_url)}">{_e(portfolio_display)}</a></span>'
        if portfolio_url else ""
    )

    # ── Build section HTML ─────────────────────────────────────────
    projects_html = _render_projects(tailored.projects)
    projects_section = (
        f'<section>\n'
        f'  <div class="section-header">Projects</div>\n'
        f'  {projects_html}\n'
        f'</section>'
        if projects_html else ""
    )

    certs_html = _render_certifications(tailored.certifications)
    certs_section = (
        f'<section>\n'
        f'  <div class="section-header">Certifications</div>\n'
        f'  {certs_html}\n'
        f'</section>'
        if certs_html else ""
    )

    # ── Replace placeholders ───────────────────────────────────────
    replacements = {
        "{{LANG}}": "en",
        "{{PAGE_WIDTH}}": "210mm",
        "{{NAME}}": _e(name),
        "{{EMAIL}}": _e(email),
        "{{LINKEDIN_URL}}": _e(linkedin_url),
        "{{LINKEDIN_DISPLAY}}": _e(linkedin_display),
        "{{LOCATION}}": _e(location),
        "{{PHONE_SPAN}}": phone_html,
        "{{PORTFOLIO_SPAN}}": portfolio_html,
        "{{SECTION_SUMMARY}}": "Professional Summary",
        "{{SUMMARY_TEXT}}": _e(tailored.professional_summary),
        "{{SECTION_COMPETENCIES}}": "Core Competencies",
        "{{COMPETENCIES}}": _render_competencies(tailored.core_competencies),
        "{{SECTION_EXPERIENCE}}": "Work Experience",
        "{{EXPERIENCE}}": _render_experience(tailored.work_experience),
        "{{PROJECTS_SECTION}}": projects_section,
        "{{SECTION_EDUCATION}}": "Education",
        "{{EDUCATION}}": _render_education(tailored.education),
        "{{CERTIFICATIONS_SECTION}}": certs_section,
        "{{SECTION_SKILLS}}": "Skills",
        "{{SKILLS}}": _render_skills(tailored.skills),
    }

    for placeholder, value in replacements.items():
        tmpl = tmpl.replace(placeholder, value)

    return tmpl


# ══════════════════════════════════════════════════════════════════════
# PDF generation via Playwright
# ══════════════════════════════════════════════════════════════════════

def generate_pdf(
    tailored: TailoredResume,
    company: str,
    job_id: Optional[int] = None,
    tailored_summary: Optional[str] = None,
) -> Path:
    """
    Fill the template and render HTML → PDF using Playwright headless Chromium.

    Args:
        tailored:         TailoredResume object from resume_tailor.tailor_resume()
        company:          Company name (used in output filename)
        job_id:           If provided, records the resume in the tailored_resumes DB table
        tailored_summary: Short summary for DB record (defaults to first sentence of summary)

    Returns:
        Path to the generated PDF file.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    profile = load_profile_yml()
    html_content = fill_template(tailored, profile)

    # ── Output path ────────────────────────────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    safe_company = re.sub(r"[^\w\-]", "_", company.strip())[:40]
    pdf_path = config.OUTPUT_DIR / f"cv-{safe_company}-{today}.pdf"
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Playwright render ──────────────────────────────────────────
    logger.info("Rendering PDF → %s", pdf_path)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            # Set content; Google Fonts CDN needs network access
            page.set_content(html_content, wait_until="networkidle")
            # Wait for fonts to finish loading
            page.evaluate("() => document.fonts.ready")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={
                    "top": "0.6in",
                    "right": "0.6in",
                    "bottom": "0.6in",
                    "left": "0.6in",
                },
            )
        finally:
            browser.close()

    size_kb = pdf_path.stat().st_size / 1024
    logger.info("PDF generated: %s (%.1f KB)", pdf_path, size_kb)

    # ── Record in database ─────────────────────────────────────────
    if job_id is not None:
        summary_for_db = tailored_summary or tailored.professional_summary[:200]
        skills_for_db = ", ".join(tailored.core_competencies)
        database.insert_tailored_resume(
            job_id=job_id,
            file_path=str(pdf_path),
            tailored_summary=summary_for_db,
            tailored_skills=skills_for_db,
        )
        logger.info("Recorded tailored resume in DB for job_id=%d", job_id)

    return pdf_path
