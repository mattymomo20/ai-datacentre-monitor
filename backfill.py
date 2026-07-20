"""One-off historical backfill: Jan 2023 -> current month.

Pulls every data centre article from the fixed outlet panel (NYT + Guardian)
month by month, classifies each headline with Claude Haiku, and stores the
labels in SQLite. Runs happily on GitHub Actions (no GDELT, no bot filters).

Resumable: completed months are recorded in the runs table and skipped on
re-run, so if it stops partway just run it again.

Run with:  python backfill.py   (or the "One-off historical backfill" Action)
"""

from datetime import datetime, timezone

from config import BACKFILL_START
from db import connect, insert_articles, month_done, record_run, now_iso
from panel_sources import fetch_month_panel
from classify import classify_all


def months_range(start: str) -> list[str]:
    """['2023-01', ..., current month]."""
    now = datetime.now(timezone.utc)
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while (y, m) <= (now.year, now.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def backfill_month(conn, month: str) -> None:
    started = now_iso()
    print(f"  [{month}] fetching panel (NYT + Guardian)...")
    articles = fetch_month_panel(month)
    # NOTE: an empty month is legitimate here — API errors raise loudly inside
    # fetch_month_panel, so reaching this point with 0 articles means both
    # archives genuinely had nothing that month (true in early 2023).
    for a in articles:
        a.update(month=month, stream="panel")
    fetched = insert_articles(conn, articles)
    print(f"  [{month}] {len(articles)} fetched, {fetched} new. Classifying...")
    classified = classify_all(conn)
    record_run(conn, "backfill-month", month, fetched, classified, started, "completed")
    print(f"  [{month}] done ({classified} classified).")


def main() -> None:
    conn = connect()
    months = months_range(BACKFILL_START)
    todo = [m for m in months if not month_done(conn, m)]
    print(f"Backfill: {len(months)} months total, {len(todo)} to do.")
    print("(NYT is rate-limited to ~5 calls/min — expect roughly 1 min per month.)\n")
    for month in todo:
        try:
            backfill_month(conn, month)
        except KeyboardInterrupt:
            print("\nInterrupted — progress saved. Run again to resume.")
            return
        except Exception as e:
            record_run(conn, "backfill-month", month, 0, 0, now_iso(), "failed", str(e))
            print(f"  [{month}] FAILED: {e} — continuing with next month.")
    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
