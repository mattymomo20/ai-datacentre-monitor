"""GDELT DOC API client — rate-limited, with retry on 429.

GDELT etiquette: free DOC API allows ~1 request per 5 seconds. Exceeding it
puts your IP in a penalty box that returns 429s for a while. We sleep between
every call and back off hard on 429.
"""

import time
from datetime import datetime

import requests

from config import GDELT_SLEEP_SECONDS, GDELT_MAX_RETRIES

DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {
    # GDELT's bot filter 429s unfamiliar user agents — identify as a browser.
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}


def _get(params: dict) -> dict:
    """One rate-limited GDELT call with retries. Returns parsed JSON (or {})."""
    for attempt in range(1, GDELT_MAX_RETRIES + 1):
        time.sleep(GDELT_SLEEP_SECONDS)
        try:
            resp = requests.get(DOC_API, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                # Retrying too soon while boxed EXTENDS the penalty — back off hard.
                wait = 180 * attempt
                print(f"    GDELT 429 (penalty box) — waiting {wait}s. "
                      "Retrying too fast extends the penalty, so patience here.")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            if not resp.text.strip():
                return {}
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"    GDELT error (attempt {attempt}/{GDELT_MAX_RETRIES}): {e}")
            time.sleep(10 * attempt)
    print("    GDELT: giving up on this call.")
    return {}


def _parse_seendate(raw: str) -> str:
    """'20230105T041500Z' -> '2023-01-05' (best effort)."""
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def fetch_articles(query: str, start: str, end: str, max_records: int) -> list[dict]:
    """Fetch articles for a datetime window.

    start/end: 'YYYYMMDDHHMMSS' strings.
    Returns list of dicts: url, title, domain, source_country, seen_date.
    """
    data = _get({
        "query": query,
        "mode": "artlist",
        "maxrecords": max_records,
        "format": "json",
        "sort": "hybridrel",
        "startdatetime": start,
        "enddatetime": end,
    })
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
            "domain": art.get("domain", ""),
            "source_country": art.get("sourcecountry", ""),
            "seen_date": _parse_seendate(art.get("seendate", "")),
        })
    return out


def fetch_timeline(query: str, mode: str, start: str, end: str) -> list[tuple]:
    """Fetch a GDELT timeline ('timelinevol' or 'timelinetone') for a window.

    Returns list of (date_iso, value). These are GDELT's own aggregates over
    ALL matching coverage — an objective, non-LLM reference series.
    """
    data = _get({
        "query": query,
        "mode": mode,
        "format": "json",
        "startdatetime": start,
        "enddatetime": end,
    })
    points = []
    for series in data.get("timeline", []):
        for p in series.get("data", []):
            date_raw = p.get("date", "")
            iso = _parse_seendate(date_raw) or date_raw[:10]
            if iso:
                points.append((iso, float(p.get("value", 0))))
        break  # first series only
    return points


def month_window(month: str) -> tuple[str, str]:
    """'2023-01' -> ('20230101000000', '20230201000000')."""
    y, m = int(month[:4]), int(month[5:7])
    start = f"{y:04d}{m:02d}01000000"
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    end = f"{y2:04d}{m2:02d}01000000"
    return start, end
