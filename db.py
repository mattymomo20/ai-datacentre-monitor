"""SQLite storage for the AI Data Centre Coverage Monitor."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    domain        TEXT,
    source_country TEXT,
    seen_date     TEXT,          -- ISO date the article was seen by GDELT
    month         TEXT,          -- YYYY-MM bucket the pull targeted
    stream        TEXT,          -- 'broad' (representative) or 'conflict' (targeted)
    fetched_at    TEXT
);

CREATE TABLE IF NOT EXISTS classifications (
    article_id    INTEGER PRIMARY KEY REFERENCES articles(id),
    relevant      INTEGER,
    stance        TEXT,
    themes        TEXT,          -- JSON list
    action        TEXT,
    country       TEXT,
    locality      TEXT,
    confidence    TEXT,
    model         TEXT,
    rubric_version TEXT,
    classified_at TEXT
);

CREATE TABLE IF NOT EXISTS timelines (
    series        TEXT,          -- 'volume' or 'tone' (from GDELT, no LLM involved)
    date          TEXT,
    value         REAL,
    PRIMARY KEY (series, date)
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT,          -- 'backfill-month' or 'daily'
    period        TEXT,          -- YYYY-MM or YYYY-MM-DD
    articles_fetched    INTEGER,
    articles_classified INTEGER,
    started_at    TEXT,
    finished_at   TEXT,
    status        TEXT,          -- 'completed' or 'failed'
    note          TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def insert_articles(conn: sqlite3.Connection, articles: list[dict]) -> int:
    """Insert articles, ignoring duplicates (by URL). Returns number inserted."""
    inserted = 0
    for a in articles:
        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (url, title, domain, source_country, seen_date, month, stream, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (a["url"], a["title"], a.get("domain", ""), a.get("source_country", ""),
             a.get("seen_date", ""), a["month"], a["stream"], now_iso()),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def unclassified_articles(conn: sqlite3.Connection, limit: int | None = None) -> list[tuple]:
    """Articles with no classification yet: (id, title, domain)."""
    q = """SELECT a.id, a.title, a.domain FROM articles a
           LEFT JOIN classifications c ON c.article_id = a.id
           WHERE c.article_id IS NULL ORDER BY a.id"""
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def save_classifications(conn: sqlite3.Connection, rows: list[dict],
                         model: str, rubric_version: str) -> int:
    saved = 0
    for r in rows:
        cur = conn.execute(
            """INSERT OR REPLACE INTO classifications
               (article_id, relevant, stance, themes, action, country, locality,
                confidence, model, rubric_version, classified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["article_id"], int(bool(r["relevant"])), r["stance"],
             json.dumps(r["themes"]), r["action"], r["country"], r["locality"],
             r["confidence"], model, rubric_version, now_iso()),
        )
        saved += cur.rowcount
    conn.commit()
    return saved


def save_timeline(conn: sqlite3.Connection, series: str, points: list[tuple]) -> None:
    """points: list of (date_iso, value)."""
    conn.executemany(
        "INSERT OR REPLACE INTO timelines (series, date, value) VALUES (?, ?, ?)",
        [(series, d, v) for d, v in points],
    )
    conn.commit()


def month_done(conn: sqlite3.Connection, month: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM runs WHERE kind='backfill-month' AND period=? AND status='completed'",
        (month,),
    ).fetchone()
    return row is not None


def record_run(conn: sqlite3.Connection, kind: str, period: str, fetched: int,
               classified: int, started_at: str, status: str, note: str = "") -> None:
    conn.execute(
        """INSERT INTO runs (kind, period, articles_fetched, articles_classified,
                             started_at, finished_at, status, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (kind, period, fetched, classified, started_at, now_iso(), status, note),
    )
    conn.commit()
