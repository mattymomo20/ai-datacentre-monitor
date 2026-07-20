"""One-off historical backfill: Jan 2023 -> current month.

For each month: pull a representative sample of data centre coverage (broad
stream) plus a targeted opposition pull (conflict stream) from GDELT, classify
every new headline with Claude Haiku, and store everything in SQLite.

Resumable: completed months are recorded in the runs table and skipped on
re-run, so if it stops partway just run it again.

Run with:  uv run backfill.py
"""

from datetime import datetime, timezone

from config import (BROAD_QUERY, CONFLICT_QUERY, BROAD_MAX_RECORDS,
                    CONFLICT_MAX_RECORDS, BACKFILL_START)
from db import connect, insert_articles, month_done, record_run, now_iso, save_timeline
from gdelt import fetch_articles, fetch_timeline, month_window
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
    start, end = month_window(month)
    print(f"  [{month}] fetching broad sample...")
    broad = fetch_articles(BROAD_QUERY, start, end, BROAD_MAX_RECORDS)
    if not broad:
        # Never record an empty month as done — GDELT was likely throttling.
        raise RuntimeError("no articles returned (GDELT throttled?) — month will be retried")
    print(f"  [{month}] fetching conflict sample...")
    conflict = fetch_articles(CONFLICT_QUERY, start, end, CONFLICT_MAX_RECORDS)

    for a in broad:
        a.update(month=month, stream="broad")
    for a in conflict:
        a.update(month=month, stream="conflict")

    fetched = insert_articles(conn, broad) + insert_articles(conn, conflict)
    print(f"  [{month}] {len(broad)} broad + {len(conflict)} conflict fetched, "
          f"{fetched} new. Classifying...")
    classified = classify_all(conn)
    record_run(conn, "backfill-month", month, fetched, classified, started, "completed")
    print(f"  [{month}] done ({classified} classified).")


def refresh_timelines(conn) -> None:
    """GDELT's own volume & tone series over the whole window — objective,
    non-LLM reference lines for the dashboard."""
    start, _ = month_window(BACKFILL_START)
    end = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    print("Fetching GDELT volume timeline...")
    vol = fetch_timeline(BROAD_QUERY, "timelinevol", start, end)
    if vol:
        save_timeline(conn, "volume", vol)
    print("Fetching GDELT tone timeline...")
    tone = fetch_timeline(BROAD_QUERY, "timelinetone", start, end)
    if tone:
        save_timeline(conn, "tone", tone)
    print(f"Timelines saved ({len(vol)} volume pts, {len(tone)} tone pts).")


def main() -> None:
    conn = connect()
    months = months_range(BACKFILL_START)
    todo = [m for m in months if not month_done(conn, m)]
    print(f"Backfill: {len(months)} months total, {len(todo)} to do.")
    print("(GDELT is rate-limited to 1 call/6s — expect roughly 1-2 min per month.)\n")
    for month in todo:
        try:
            backfill_month(conn, month)
        except KeyboardInterrupt:
            print("\nInterrupted — progress saved. Run again to resume.")
            return
        except Exception as e:
            record_run(conn, "backfill-month", month, 0, 0, now_iso(), "failed", str(e))
            print(f"  [{month}] FAILED: {e} — continuing with next month.")
    refresh_timelines(conn)
    print("\nBackfill complete. Launch the dashboard with:")
    print("  uv run streamlit run dashboard.py")


if __name__ == "__main__":
    main()
