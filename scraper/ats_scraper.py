import asyncio
import aiohttp
import logging
import yaml
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
import re

import config
import database
from scraper.api_sources import normalize_job

logger = logging.getLogger(__name__)

# Constants
PORTALS_FILE = config.BASE_DIR / "portals.yaml"

class ATSSniffer:
    def __init__(self):
        self.config = self._load_config()
        self.positive_filters = self.config.get("title_filter", {}).get("positive", [])
        self.negative_filters = self.config.get("title_filter", {}).get("negative", [])

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(PORTALS_FILE, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load portals.yaml: {e}")
            return {"companies": []}

    def _matches_filters(self, title: str) -> bool:
        """Check if title passes positive and negative filters."""
        title_lower = title.lower()
        
        # Check positive filters (must match at least one)
        has_positive = False
        for p in self.positive_filters:
            if re.search(r'\b' + re.escape(p) + r'\b', title_lower):
                has_positive = True
                break
                
        if not has_positive:
            return False
            
        # Check negative filters (must not match any)
        for n in self.negative_filters:
            if re.search(r'\b' + re.escape(n) + r'\b', title_lower):
                return False
                
        return True

    def _detect_ats(self, careers_url: str) -> Tuple[str, str]:
        """Detect ATS type and slug from careers URL."""
        parsed = urlparse(careers_url)
        netloc = parsed.netloc
        path = parsed.path.strip("/")
        
        if "greenhouse.io" in netloc:
            slug = path.split("/")[-1]
            return "greenhouse", slug
        elif "lever.co" in netloc:
            slug = path.split("/")[-1]
            return "lever", slug
        elif "ashbyhq.com" in netloc:
            slug = path.split("/")[-1]
            return "ashby", slug
        elif "smartrecruiters.com" in netloc:
            slug = path.split("/")[-1]
            return "smartrecruiters", slug
            
        return "unknown", ""

    async def _fetch_greenhouse(self, session: aiohttp.ClientSession, company_name: str, slug: str) -> List[Dict[str, Any]]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        jobs = []
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return jobs
                data = await resp.json()
                
                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    if self._matches_filters(title):
                        jobs.append(normalize_job(
                            title=title,
                            company=company_name,
                            location=job.get("location", {}).get("name", ""),
                            description="", # Greenhouse boards list doesn't include full desc
                            job_url=job.get("absolute_url", ""),
                            source="greenhouse",
                            date_posted=job.get("updated_at", None)
                        ))
        except Exception as e:
            logger.debug(f"Error fetching Greenhouse for {company_name}: {e}")
        return jobs

    async def _fetch_lever(self, session: aiohttp.ClientSession, company_name: str, slug: str) -> List[Dict[str, Any]]:
        url = f"https://api.lever.co/v0/postings/{slug}"
        jobs = []
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return jobs
                data = await resp.json()
                
                for job in data:
                    title = job.get("text", "")
                    if self._matches_filters(title):
                        jobs.append(normalize_job(
                            title=title,
                            company=company_name,
                            location=job.get("categories", {}).get("location", ""),
                            description=job.get("descriptionPlain", ""),
                            job_url=job.get("hostedUrl", ""),
                            source="lever",
                            date_posted=None,
                            job_type=job.get("categories", {}).get("commitment", "")
                        ))
        except Exception as e:
            logger.debug(f"Error fetching Lever for {company_name}: {e}")
        return jobs

    async def _fetch_ashby(self, session: aiohttp.ClientSession, company_name: str, slug: str) -> List[Dict[str, Any]]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        jobs = []
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return jobs
                data = await resp.json()
                
                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    if self._matches_filters(title):
                        jobs.append(normalize_job(
                            title=title,
                            company=company_name,
                            location=job.get("location", ""),
                            description="", # Ashby list doesn't always have full desc
                            job_url=job.get("jobUrl", ""),
                            source="ashby",
                            date_posted=job.get("publishedAt", None)
                        ))
        except Exception as e:
            logger.debug(f"Error fetching Ashby for {company_name}: {e}")
        return jobs

    async def fetch_company_jobs(self, session: aiohttp.ClientSession, company: Dict[str, Any], semaphore: asyncio.Semaphore) -> List[Dict[str, Any]]:
        name = company.get("name")
        careers_url = company.get("careers_url")
        enabled = company.get("enabled", True)
        
        if not enabled or not careers_url:
            return []
            
        ats_type, slug = self._detect_ats(careers_url)
        if not slug or ats_type == "unknown":
            logger.warning(f"Could not detect ATS for {name} ({careers_url})")
            return []
            
        async with semaphore:
            if ats_type == "greenhouse":
                return await self._fetch_greenhouse(session, name, slug)
            elif ats_type == "lever":
                return await self._fetch_lever(session, name, slug)
            elif ats_type == "ashby":
                return await self._fetch_ashby(session, name, slug)
            else:
                return []

    async def fetch_all(self) -> List[Dict[str, Any]]:
        companies = self.config.get("companies", [])
        semaphore = asyncio.Semaphore(10) # Max 10 concurrent requests
        
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_company_jobs(session, c, semaphore) for c in companies]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        all_jobs = []
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Error in async fetch: {result}")
                
        return all_jobs


def run_ats_scraper() -> int:
    """Run the unified ATS scraper and store results in DB."""
    logger.info("=" * 60)
    logger.info("STARTING UNIFIED ATS SCRAPER")
    logger.info("=" * 60)
    
    sniffer = ATSSniffer()
    
    # Run async loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    jobs = loop.run_until_complete(sniffer.fetch_all())
    
    inserted = 0
    for job in jobs:
        job_id = database.insert_job(**job)
        if job_id:
            inserted += 1
            
    logger.info(f"ATS SCRAPER COMPLETE — {inserted} new jobs added (out of {len(jobs)} found)")
    return inserted

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ats_scraper()
