"""Daily incremental run (used by the GitHub Action).

Uses NewsAPI (broad, ~150k outlets, reliable from GitHub runners). Pulls the
last 2 days of coverage (overlap protects against gaps; URL dedup prevents
double counting) and classifies new headlines.

GDELT is deliberately NOT called here: its free tier throttles GitHub's
shared runner IPs, which stalls the whole run.

Run with:  uv run daily.py
"""

from datetime import datetime, timedelta, timezone

from db import connect, insert_articles, record_run, now_iso
from newsapi import (fetch_articles, BROAD_QUERY_NEWSAPI, CONFLICT_QUERY_NEWSAPI)
from panel_sources import fetch_window_panel
from classify import classify_all

DAILY_BROAD_MAX = 100
DAILY_CONFLICT_MAX = 100


def main() -> None:
    conn = connect()
    started = now_iso()
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    print("Fetching latest broad sample (NewsAPI)...")
    broad = fetch_articles(BROAD_QUERY_NEWSAPI, from_date, to_date, DAILY_BROAD_MAX)
    print("Fetching latest conflict sample (NewsAPI)...")
    conflict = fetch_articles(CONFLICT_QUERY_NEWSAPI, from_date, to_date, DAILY_CONFLICT_MAX)
    print("Fetching latest panel articles (NYT + Guardian)...")
    panel = fetch_window_panel(from_date, to_date)

    for a in broad:
        a.update(month=month, stream="broad")
    for a in conflict:
        a.update(month=month, stream="conflict")
    for a in panel:
        a.update(month=month, stream="panel")

    fetched = (insert_articles(conn, broad) + insert_articles(conn, conflict)
               + insert_articles(conn, panel))
    print(f"{len(broad)} broad + {len(conflict)} conflict fetched, {fetched} new. Classifying...")
    classified = classify_all(conn)
    record_run(conn, "daily", now.strftime("%Y-%m-%d"), fetched, classified,
               started, "completed")
    print(f"Daily run done: {fetched} new articles, {classified} classified.")


if __name__ == "__main__":
    main()
