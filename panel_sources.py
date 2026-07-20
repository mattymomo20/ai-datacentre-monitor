"""Fixed outlet panel: NYT + Guardian.

These two archives are free, reliable, and reachable from GitHub Actions —
no bot-filter roulette. Together they form a consistent "measurement panel"
across the whole 2023 -> today window and every day going forward, which is
what makes the stance trend comparable over time.

Rate limits respected: NYT Article Search ~5 req/min (12s spacing),
Guardian developer tier ~1 req/sec (2s spacing to be polite).
"""

import calendar
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

NYT_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
GUARDIAN_URL = "https://content.guardianapis.com/search"

# Lucene syntax: terms inside parens are OR'd within the field
NYT_FQ = ('headline:("data center" "data centre" "datacenter") '
          'OR body:("data center" "data centre" "datacenter")')
GUARDIAN_Q = '"data centre" OR "data center" OR "datacenter"'

NYT_SLEEP = 12
NYT_MAX_PAGES = 5        # 10 results/page -> up to 50 NYT articles per window
GUARDIAN_SLEEP = 2
GUARDIAN_MAX_PAGES = 4   # 50 results/page -> up to 200 Guardian articles per window


def _get(url: str, params: dict, sleep: float) -> dict:
    """One polite request with a single retry on 429/5xx."""
    for attempt in (1, 2):
        time.sleep(sleep)
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            print(f"    {resp.status_code} from {url.split('/')[2]} — waiting 60s...")
            time.sleep(60)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def fetch_nyt(from_ymd: str, to_ymd: str) -> list[dict]:
    """from/to as YYYYMMDD strings (NYT format)."""
    key = os.environ.get("NYT_API_KEY")
    if not key:
        raise SystemExit("NYT_API_KEY not set — check .env / GitHub secret.")
    out = []
    for page in range(NYT_MAX_PAGES):
        data = _get(NYT_URL, {
            "fq": NYT_FQ,
            "begin_date": from_ymd,
            "end_date": to_ymd,
            "sort": "oldest",
            "page": page,
            "api-key": key,
        }, NYT_SLEEP)
        docs = (data.get("response") or {}).get("docs") or []
        for d in docs:
            title = ((d.get("headline") or {}).get("main") or "").strip()
            url = d.get("web_url", "")
            if title and url:
                out.append({
                    "url": url,
                    "title": title,
                    "domain": "nytimes.com",
                    "source_country": "United States",
                    "seen_date": (d.get("pub_date") or "")[:10],
                })
        if len(docs) < 10:
            break
    return out


def fetch_guardian(from_iso: str, to_iso: str) -> list[dict]:
    """from/to as YYYY-MM-DD strings (Guardian format)."""
    key = os.environ.get("GUARDIAN_API_KEY")
    if not key:
        raise SystemExit("GUARDIAN_API_KEY not set — check .env / GitHub secret.")
    out = []
    for page in range(1, GUARDIAN_MAX_PAGES + 1):
        data = _get(GUARDIAN_URL, {
            "q": GUARDIAN_Q,
            "from-date": from_iso,
            "to-date": to_iso,
            "page-size": 50,
            "page": page,
            "api-key": key,
        }, GUARDIAN_SLEEP)
        resp = data.get("response") or {}
        for r in resp.get("results") or []:
            title = (r.get("webTitle") or "").strip()
            url = r.get("webUrl", "")
            if title and url:
                out.append({
                    "url": url,
                    "title": title,
                    "domain": "theguardian.com",
                    "source_country": "United Kingdom",
                    "seen_date": (r.get("webPublicationDate") or "")[:10],
                })
        if page >= int(resp.get("pages") or 1):
            break
    return out


def month_bounds(month: str) -> tuple[str, str]:
    """'2023-01' -> ('2023-01-01', '2023-01-31')."""
    y, m = int(month[:4]), int(month[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def fetch_month_panel(month: str) -> list[dict]:
    start, end = month_bounds(month)
    nyt = fetch_nyt(start.replace("-", ""), end.replace("-", ""))
    print(f"    NYT: {len(nyt)} articles")
    gua = fetch_guardian(start, end)
    print(f"    Guardian: {len(gua)} articles")
    return nyt + gua


def fetch_window_panel(from_iso: str, to_iso: str) -> list[dict]:
    nyt = fetch_nyt(from_iso.replace("-", ""), to_iso.replace("-", ""))
    gua = fetch_guardian(from_iso, to_iso)
    return nyt + gua
