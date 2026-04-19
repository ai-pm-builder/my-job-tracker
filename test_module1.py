"""Quick test for Module 1 — Greenhouse and Lever scrapers."""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    stream=sys.stdout,
)

import database
from scraper.greenhouse_scraper import run_greenhouse_scraper
from scraper.lever_scraper import run_lever_scraper
from scraper import company_list

# --- Test Greenhouse (first 3 companies) ---
print("=" * 50)
print("Testing Greenhouse Scraper (3 companies)")
print("=" * 50)
original_gh = company_list.GREENHOUSE_COMPANIES
company_list.GREENHOUSE_COMPANIES = original_gh[:3]
gh_count = run_greenhouse_scraper()
company_list.GREENHOUSE_COMPANIES = original_gh
print(f"Greenhouse result: {gh_count} new PM jobs\n")

# --- Test Lever (first 3 companies) ---
print("=" * 50)
print("Testing Lever Scraper (3 companies)")
print("=" * 50)
original_lv = company_list.LEVER_COMPANIES
company_list.LEVER_COMPANIES = original_lv[:3]
lv_count = run_lever_scraper()
company_list.LEVER_COMPANIES = original_lv
print(f"Lever result: {lv_count} new PM jobs\n")

# --- DB Stats ---
print("=" * 50)
stats = database.get_job_stats()
print(f"Total jobs in DB: {stats['total_jobs']}")
print(f"By source: {stats['by_source']}")

# Show some sample jobs
jobs = database.get_all_jobs(limit=5)
if jobs:
    print(f"\nSample jobs:")
    for j in jobs:
        print(f"  - {j['title']} @ {j['company']} [{j['source']}]")
else:
    print("\nNo PM jobs found on tested companies (this is normal if they have no open PM roles)")

print("\n✅ Module 1 test complete!")
