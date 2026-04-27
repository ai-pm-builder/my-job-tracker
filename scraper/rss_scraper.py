import feedparser
import logging
import requests
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
import re

import config
from scraper.api_sources import normalize_job, is_pm_role

logger = logging.getLogger(__name__)

def extract_actual_url(google_url: str) -> str:
    """Extract the actual destination URL from a Google Alert URL."""
    # Google Alert URLs usually look like: https://www.google.com/url?q=ACTUAL_URL&ct=...
    match = re.search(r'url\?q=(.+?)&ct=', google_url)
    if match:
        import urllib.parse
        return urllib.parse.unquote(match.group(1))
    return google_url

def parse_rss_feed(feed_url: str) -> List[Dict[str, Any]]:
    """Parse a single RSS feed and extract PM jobs."""
    jobs = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            
            # Google Alerts usually format titles like: "Senior Product Manager - Google - Bangalore"
            # It wraps matching keywords in <b> tags sometimes in the XML, so we clean it.
            clean_title = BeautifulSoup(title, "html.parser").get_text()
            
            # Use the existing is_pm_role to filter
            if is_pm_role(clean_title):
                raw_url = entry.link
                job_url = extract_actual_url(raw_url)
                
                # Try to extract company from title if it follows a pattern
                company = ""
                parts = clean_title.split(" - ")
                if len(parts) >= 2:
                    company = parts[1].strip()
                    clean_title = parts[0].strip()
                
                # The description in RSS is a snippet
                snippet = BeautifulSoup(entry.summary, "html.parser").get_text()
                
                date_posted = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    from datetime import timezone
                    import time
                    date_posted = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc).isoformat()
                
                jobs.append(normalize_job(
                    title=clean_title,
                    company=company,
                    location="",  # Hard to extract reliably from just the alert
                    description=snippet,
                    job_url=job_url,
                    source="rss_google_alerts",
                    date_posted=date_posted,
                ))
    except Exception as e:
        logger.error(f"Error parsing RSS feed {feed_url}: {e}")
        
    return jobs

def fetch_all_rss_jobs() -> List[Dict[str, Any]]:
    """Fetch jobs from all configured RSS feeds."""
    all_jobs = []
    
    if not hasattr(config, 'GOOGLE_ALERTS_RSS_URLS') or not config.GOOGLE_ALERTS_RSS_URLS:
        logger.info("No Google Alerts RSS URLs configured. Skipping.")
        return all_jobs
        
    for feed_url in config.GOOGLE_ALERTS_RSS_URLS:
        logger.info(f"Parsing RSS feed: {feed_url}")
        all_jobs.extend(parse_rss_feed(feed_url))
        
    logger.info(f"Fetched {len(all_jobs)} jobs from RSS feeds total.")
    return all_jobs

def run_rss_scraper() -> int:
    """Fetch jobs from RSS feeds and insert into database."""
    import database
    jobs = fetch_all_rss_jobs()
    inserted = 0
    for job in jobs:
        job_id = database.insert_job(**job)
        if job_id:
            inserted += 1
            
    if hasattr(config, 'GOOGLE_ALERTS_RSS_URLS') and config.GOOGLE_ALERTS_RSS_URLS:
        logger.info(f"Inserted {inserted} new jobs from RSS feeds into the database.")
    return inserted

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test with a dummy or sample feed if one is configured
    if hasattr(config, 'GOOGLE_ALERTS_RSS_URLS') and config.GOOGLE_ALERTS_RSS_URLS:
        run_rss_scraper()
    else:
        print("Add a feed URL to GOOGLE_ALERTS_RSS_URLS in config.py to test.")
