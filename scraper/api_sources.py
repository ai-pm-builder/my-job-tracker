import requests
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Basic keywords for PM filtering
PM_KEYWORDS = [
    "product manager",
    "product management",
    "pm",
    "head of product",
    "vp of product",
    "director of product"
]

import re
import config

def is_pm_role(title: str) -> bool:
    """Check if a job title is a Product Management role and passes negative filters."""
    title_lower = title.lower()
    
    # Check negative filters
    if hasattr(config, "NEGATIVE_KEYWORDS"):
        for negative in config.NEGATIVE_KEYWORDS:
            if re.search(r'\b' + re.escape(negative) + r'\b', title_lower):
                return False
                
    # Check positive filters
    for keyword in PM_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', title_lower):
            return True
            
    return False

def normalize_job(
    title: str,
    company: str,
    location: str,
    description: str,
    job_url: str,
    source: str,
    job_type: str = None,
    salary: str = None,
    date_posted: str = None,
    is_remote: bool = False,
    company_url: str = None,
    logo_url: str = None,
) -> Dict[str, Any]:
    """Normalize job data into a consistent dictionary format."""
    return {
        "title": title or "",
        "company": company or "",
        "location": location or "",
        "description": description or "",
        "job_url": job_url or "",
        "source": source or "",
        "job_type": job_type,
        "salary": salary,
        "date_posted": date_posted,
        "is_remote": is_remote,
        "company_url": company_url,
        "logo_url": logo_url,
    }

def fetch_himalayas_jobs() -> List[Dict[str, Any]]:
    """Fetch jobs from Himalayas API."""
    url = "https://himalayas.app/jobs/api"
    jobs = []
    
    try:
        limit = 100
        offset = 0
        
        while True:
            response = requests.get(f"{url}?limit={limit}&offset={offset}")
            response.raise_for_status()
            data = response.json()
            
            for job in data.get("jobs", []):
                title = job.get("title", "")
                
                if is_pm_role(title):
                    company = job.get("companyName", "")
                    location = job.get("locationRestrictions", [])
                    location_str = ", ".join(location) if location else "Remote"
                    description = job.get("description", "")
                    job_url = job.get("applicationLink", job.get("himalayasLink", ""))
                    
                    min_salary = job.get("minSalary")
                    max_salary = job.get("maxSalary")
                    salary = f"${min_salary} - ${max_salary}" if min_salary and max_salary else None
                    
                    date_posted = datetime.fromtimestamp(job.get("pubDate", 0), tz=timezone.utc).isoformat() if job.get("pubDate") else None
                    
                    jobs.append(normalize_job(
                        title=title,
                        company=company,
                        location=location_str,
                        description=description,
                        job_url=job_url,
                        source="himalayas",
                        salary=salary,
                        date_posted=date_posted,
                        is_remote=True,
                        logo_url=job.get("companyLogo")
                    ))
                    
            if offset + limit >= data.get("total", 0) or offset >= 500: # Limit to 5 pages
                break
            offset += limit
            
    except Exception as e:
        logger.error(f"Error fetching from Himalayas: {e}")
        
    return jobs

def fetch_arbeitnow_jobs() -> List[Dict[str, Any]]:
    """Fetch jobs from Arbeitnow API."""
    url = "https://www.arbeitnow.com/api/job-board-api"
    jobs = []
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        for job in data.get("data", []):
            title = job.get("title", "")
            
            if is_pm_role(title):
                jobs.append(normalize_job(
                    title=title,
                    company=job.get("company_name", ""),
                    location=job.get("location", ""),
                    description=job.get("description", ""),
                    job_url=job.get("url", ""),
                    source="arbeitnow",
                    job_type=job.get("job_types", [""])[0] if job.get("job_types") else None,
                    date_posted=datetime.fromtimestamp(job.get("created_at", 0), tz=timezone.utc).isoformat() if job.get("created_at") else None,
                    is_remote=job.get("remote", False)
                ))
                
    except Exception as e:
        logger.error(f"Error fetching from Arbeitnow: {e}")
        
    return jobs

def fetch_remoteok_jobs() -> List[Dict[str, Any]]:
    """Fetch jobs from RemoteOK API."""
    url = "https://remoteok.com/api"
    jobs = []
    
    try:
        headers = {"User-Agent": "Job Tracker"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        for item in data:
            if item.get("legal") == "Notice":
                continue
                
            title = item.get("position", "")
            
            if is_pm_role(title):
                jobs.append(normalize_job(
                    title=title,
                    company=item.get("company", ""),
                    location=item.get("location", ""),
                    description=item.get("description", ""),
                    job_url=item.get("url", ""),
                    source="remoteok",
                    job_type=None,
                    salary=f"${item.get('salary_min')} - ${item.get('salary_max')}" if item.get('salary_min') and item.get('salary_max') else None,
                    date_posted=item.get("date"),
                    is_remote=True,
                    company_url=item.get("company_logo")
                ))
                
    except Exception as e:
        logger.error(f"Error fetching from RemoteOK: {e}")
        
    return jobs

def fetch_all_api_jobs() -> List[Dict[str, Any]]:
    """Fetch jobs from all configured free APIs."""
    all_jobs = []
    
    logger.info("Fetching jobs from Himalayas...")
    all_jobs.extend(fetch_himalayas_jobs())
    
    logger.info("Fetching jobs from Arbeitnow...")
    all_jobs.extend(fetch_arbeitnow_jobs())
    
    logger.info("Fetching jobs from RemoteOK...")
    all_jobs.extend(fetch_remoteok_jobs())
    
    logger.info(f"Fetched {len(all_jobs)} PM jobs from free APIs total.")
    return all_jobs

def run_api_scraper() -> int:
    """Fetch jobs from all free APIs and insert into database."""
    import database
    jobs = fetch_all_api_jobs()
    inserted = 0
    for job in jobs:
        job_id = database.insert_job(**job)
        if job_id:
            inserted += 1
    logger.info(f"Inserted {inserted} new PM jobs from free APIs into the database.")
    return inserted

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_api_scraper()
