"""
Target companies for Greenhouse and Lever career page scraping.
Add or remove companies as needed — the scraper will iterate through these lists.

Format:
  - GREENHOUSE_COMPANIES: List of (company_name, board_slug) tuples
    → URL pattern: https://boards.greenhouse.io/{board_slug}
  - LEVER_COMPANIES: List of (company_name, company_slug) tuples
    → URL pattern: https://jobs.lever.co/{company_slug}
"""

# ──────────────────────────── Greenhouse Companies ────────────────────────────
# These companies host their career pages on boards.greenhouse.io
GREENHOUSE_COMPANIES = [
    ("Stripe", "stripe"),
    ("Airbnb", "airbnb"),
    ("Notion", "notion"),
    ("Figma", "figma"),
    ("Coinbase", "coinbase"),
    ("Discord", "discord"),
    ("Instacart", "instacart"),
    ("Plaid", "plaid"),
    ("Airtable", "airtable"),
    ("Canva", "canva"),
    ("Databricks", "databricks"),
    ("HashiCorp", "hashicorp"),
    ("Gitlab", "gitlab"),
    ("Snyk", "snyk"),
    ("Elastic", "elastic"),
    ("MongoDB", "mongodb"),
    ("Cloudflare", "cloudflare"),
    ("Twilio", "twilio"),
    ("HubSpot", "hubspot"),
    ("Razorpay", "razorpay"),
    ("CRED", "cred"),
    ("Zerodha", "zerodha"),
    ("PhonePe", "phonepe"),
    ("Swiggy", "swiggy"),
    ("Meesho", "meesho"),
]

# ──────────────────────────── Lever Companies ────────────────────────────
# These companies host their career pages on jobs.lever.co
LEVER_COMPANIES = [
    ("Netflix", "netflix"),
    ("Spotify", "spotify"),
    ("Shopify", "shopify"),
    ("Lyft", "lyft"),
    ("Reddit", "reddit"),
    ("Scale AI", "scaleai"),
    ("Rippling", "rippling"),
    ("Verkada", "verkada"),
    ("Loom", "loom"),
    ("Faire", "faire"),
    ("Postman", "postman"),
    ("Groww", "groww"),
    ("Unacademy", "unacademy"),
    ("Dream11", "dream11"),
    ("Jupiter", "jupiter-money"),
    ("Slice", "sliceit"),
]

# ──────────────────────────── Product Manager Keywords ────────────────────────────
# Used to filter job listings from Greenhouse/Lever for PM-related roles
PM_KEYWORDS = [
    "product manager",
    "senior product manager",
    "lead product manager",
    "principal product manager",
    "group product manager",
    "director of product",
    "head of product",
    "vp product",
]
