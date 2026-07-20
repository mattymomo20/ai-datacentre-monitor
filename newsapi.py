"""NewsAPI client for the daily incremental pull.

NewsAPI (newsapi.org) indexes ~150k outlets — broad coverage, and it works
reliably from GitHub Actions runners (proven by the political-risk terminal's
daily runs). Free-tier limits: ~100 requests/day, 100 results per query,
archive only ~1 month back — fine for a daily pull, useless for backfill.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

EVERYTHING = "https://newsapi.org/v2/everything"

BROAD_QUERY_NEWSAPI = '"data center" OR "data centre" OR datacenter OR hyperscale'
CONFLICT_QUERY_NEWSAPI = (
    '("data center" OR "data centre" OR datacenter) AND '
    '(protest OR moratorium OR lawsuit OR opposition OR rezoning OR blocked '
    'OR rejected OR backlash OR "water use" OR "power grid" OR noise)'
)


def fetch_articles(query: str, from_date: str, to_date: str,
                   max_records: int = 100) -> list[dict]:
    """Fetch articles for a date window (YYYY-MM-DD strings).

    Returns the same dict shape the GDELT client produces:
    url, title, domain, source_country, seen_date.
    """
    key = os.environ.get("NEWSAPI_KEY")
    if not key:
        raise SystemExit("NEWSAPI_KEY not set — check your .env / GitHub secret.")
    resp = requests.get(EVERYTHING, params={
        "q": query,
        "from": from_date,
        "to": to_date,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": min(max_records, 100),
        "apiKey": key,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {data.get('code')} {data.get('message')}")
    out, seen = [], set()
    for art in data.get("articles", []):
        url = art.get("url", "")
        title = (art.get("title") or "").strip()
        if not url or not title or url in seen:
            continue
        seen.add(url)
        out.append({
            "url": url,
            "title": title,
            "domain": (art.get("source") or {}).get("name", ""),
            "source_country": "",
            "seen_date": (art.get("publishedAt") or "")[:10],
        })
    return out
