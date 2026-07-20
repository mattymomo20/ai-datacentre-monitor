"""Daily incremental run (used by the GitHub Action).

Pulls the last 2 days of coverage (overlap protects against gaps; URL
dedup prevents double counting), classifies new headlines, and refreshes
the GDELT timelines.

Run with:  uv run daily.py
"""

from datetime import datetime, timedelta, timezone

from config import (BROAD_QUERY, CONFLICT_QUERY, BACKFILL_START)
from db import connect, insert_articles, record_run, now_iso
from gdelt import fetch_articles
from classify import classify_all
from backfill import refresh_timelines

DAILY_BROAD_MAX = 100
DAILY_CONFLICT_MAX = 50


def main() -> None:
    conn = connect()
    started = now_iso()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).strftime("%Y%m%d%H%M%S")
    end = now.strftime("%Y%m%d%H%M%S")
    month = now.strftime("%Y-%m")

    print("Fetching latest broad sample...")
    broad = fetch_articles(BROAD_QUERY, start, end, DAILY_BROAD_MAX)
    print("Fetching latest conflict sample...")
    conflict = fetch_articles(CONFLICT_QUERY, start, end, DAILY_CONFLICT_MAX)

    for a in broad:
        a.update(month=month, stream="broad")
    for a in conflict:
        a.update(month=month, stream="conflict")

    fetched = insert_articles(conn, broad) + insert_articles(conn, conflict)
    print(f"{fetched} new articles. Classifying...")
    classified = classify_all(conn)
    refresh_timelines(conn)
    record_run(conn, "daily", now.strftime("%Y-%m-%d"), fetched, classified,
               started, "completed")
    print(f"Daily run done: {fetched} fetched, {classified} classified.")


if __name__ == "__main__":
    main()
