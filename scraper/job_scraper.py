"""
Main job scraper using python-jobspy library.
Scrapes jobs from LinkedIn, Indeed, Glassdoor, Google Jobs, and Naukri.
"""

import logging
import pandas as pd

import config
import database

logger = logging.getLogger(__name__)


def _scrape_single_search(search_term: str, location: str) -> pd.DataFrame:
    """
    Run a single scrape_jobs call for one search term + location combo.
    Returns a DataFrame of results (may be empty).
    """
    try:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.error("python-jobspy is not installed or broken. Skipping JobSpy scrape.")
            return pd.DataFrame()
            
        # Separate Google search from other sites
        non_google_sites = [s for s in config.JOBSPY_SITES if s != "google"]
        google_included = "google" in config.JOBSPY_SITES

        frames = []

        # Scrape non-Google sites
        if non_google_sites:
            logger.info(
                "Scraping %s for '%s' in '%s'...",
                non_google_sites, search_term, location,
            )
            try:
                df = scrape_jobs(
                    site_name=non_google_sites,
                    search_term=search_term,
                    location=location,
                    results_wanted=config.RESULTS_WANTED,
                    hours_old=config.HOURS_OLD,
                    country_indeed=config.COUNTRY_INDEED,
                    is_remote=config.IS_REMOTE,
                )
                if df is not None and not df.empty:
                    frames.append(df)
                    logger.info("  → Got %d results from non-Google sites", len(df))
            except Exception as e:
                logger.warning("  → Non-Google scrape failed: %s", e)

        # Scrape Google Jobs separately (requires google_search_term)
        if google_included:
            google_term = f"{search_term} jobs in {location}"
            logger.info("Scraping Google Jobs for '%s'...", google_term)
            try:
                df = scrape_jobs(
                    site_name=["google"],
                    google_search_term=google_term,
                    location=location,
                    results_wanted=config.RESULTS_WANTED,
                    hours_old=config.HOURS_OLD,
                )
                if df is not None and not df.empty:
                    frames.append(df)
                    logger.info("  → Got %d results from Google Jobs", len(df))
            except Exception as e:
                logger.warning("  → Google Jobs scrape failed: %s", e)

        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()

    except Exception as e:
        logger.error("Scrape failed for '%s' in '%s': %s", search_term, location, e)
        return pd.DataFrame()


def _store_jobs(df: pd.DataFrame, source_label: str = "jobspy") -> int:
    """
    Store scraped jobs from a DataFrame into the database.
    Returns count of new (non-duplicate) jobs inserted.
    """
    if df.empty:
        return 0

    new_count = 0
    for _, row in df.iterrows():
        # Extract fields — jobspy returns these column names
        title = str(row.get("title", "")).strip()
        company = str(row.get("company_name", row.get("company", ""))).strip()
        location = str(row.get("location", "")).strip()
        description = str(row.get("description", "")).strip()
        job_url = str(row.get("job_url", row.get("job_url_direct", ""))).strip()
        source = str(row.get("site", source_label)).strip()
        job_type = str(row.get("job_type", "")).strip() or None
        salary_raw = row.get("min_amount", None)
        salary = None
        if salary_raw and pd.notna(salary_raw):
            max_amt = row.get("max_amount", "")
            currency = row.get("currency", "")
            salary = f"{currency} {salary_raw}"
            if max_amt and pd.notna(max_amt):
                salary += f" - {max_amt}"

        date_posted = str(row.get("date_posted", "")).strip() or None
        is_remote = bool(row.get("is_remote", False))
        company_url = str(row.get("company_url", "")).strip() or None
        logo_url = str(row.get("logo_photo_url", "")).strip() or None

        if not title or not job_url or job_url == "nan":
            continue
            
        # Apply negative filters
        skip = False
        if hasattr(config, "NEGATIVE_KEYWORDS"):
            title_lower = title.lower()
            import re
            for negative in config.NEGATIVE_KEYWORDS:
                if re.search(r'\b' + re.escape(negative) + r'\b', title_lower):
                    skip = True
                    break
        
        if skip:
            continue

        job_id = database.insert_job(
            title=title,
            company=company,
            location=location,
            description=description,
            job_url=job_url,
            source=source,
            job_type=job_type,
            salary=salary,
            date_posted=date_posted,
            is_remote=is_remote,
            company_url=company_url,
            logo_url=logo_url,
        )
        if job_id is not None:
            new_count += 1

    return new_count


def run_jobspy_scraper() -> int:
    """
    Run the full jobspy scraper across all search terms and locations.
    Returns total count of new jobs inserted.
    """
    logger.info("=" * 60)
    logger.info("STARTING JOBSPY SCRAPER")
    logger.info("=" * 60)

    # Circuit breaker logic
    import json
    import time
    breaker_file = config.DATA_DIR / "jobspy_breaker.json"
    
    if breaker_file.exists():
        try:
            with open(breaker_file, "r") as f:
                breaker_state = json.load(f)
            
            if breaker_state.get("failures", 0) >= 3:
                last_failure = breaker_state.get("last_failure", 0)
                if time.time() - last_failure < 24 * 3600:
                    logger.warning("JobSpy circuit breaker is OPEN (failed 3+ times). Skipping for 24 hours.")
                    return 0
                else:
                    logger.info("JobSpy circuit breaker RESET (24 hours passed).")
                    breaker_state = {"failures": 0, "last_failure": 0}
                    with open(breaker_file, "w") as f:
                        json.dump(breaker_state, f)
        except Exception as e:
            logger.debug(f"Circuit breaker check failed: {e}")

    total_new = 0
    failures_in_run = 0

    for search_term in config.SEARCH_TERMS:
        for location in config.LOCATIONS:
            df = _scrape_single_search(search_term, location)
            if not df.empty:
                new = _store_jobs(df)
                total_new += new
                logger.info(
                    "  Stored %d new jobs for '%s' in '%s' (%d total rows)",
                    new, search_term, location, len(df),
                )
            else:
                logger.info(
                    "  No results for '%s' in '%s'", search_term, location,
                )
                failures_in_run += 1

    # If everything failed or we caught exceptions, increment global breaker
    total_searches = len(config.SEARCH_TERMS) * len(config.LOCATIONS)
    if failures_in_run >= total_searches and total_searches > 0:
        logger.warning("JobSpy returned no results for any search. Recording failure.")
        try:
            import json
            import time
            breaker_state = {"failures": 0, "last_failure": 0}
            if breaker_file.exists():
                with open(breaker_file, "r") as f:
                    breaker_state = json.load(f)
            
            breaker_state["failures"] = breaker_state.get("failures", 0) + 1
            breaker_state["last_failure"] = time.time()
            
            with open(breaker_file, "w") as f:
                json.dump(breaker_state, f)
        except Exception as e:
            logger.debug(f"Failed to update circuit breaker: {e}")

    logger.info("JOBSPY SCRAPER COMPLETE — %d new jobs added", total_new)
    return total_new
