"""Headline classification with Claude Haiku.

Batches headlines into one prompt, asks for strict JSON labels per the rubric
in classification_rubric.md, validates every field against the fixed sets in
config.py, and returns rows ready for db.save_classifications().
"""

import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from config import MODEL, RUBRIC_VERSION, BATCH_SIZE, STANCES, THEMES, ACTIONS

load_dotenv()

RUBRIC = Path(__file__).with_name("classification_rubric.md").read_text()

SYSTEM = (
    "You label news headlines about data centres for an insurance underwriting "
    "desk. Follow the rubric exactly. Output ONLY a JSON array — no prose, no "
    "markdown fences.\n\n" + RUBRIC
)


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY not set — check your .env file.")
    return anthropic.Anthropic(api_key=key)


def _extract_json(text: str) -> list:
    """Parse the model's output into a list, tolerating stray fences/prose."""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON array in model output")
    return json.loads(m.group(0))


def _validate(item: dict, article_id: int) -> dict:
    """Coerce one model answer into a safe, schema-conformant row."""
    stance = item.get("stance", "neutral")
    if stance not in STANCES:
        stance = "neutral"
    themes = [t for t in (item.get("themes") or []) if t in THEMES][:3]
    action = item.get("action", "none")
    if action not in ACTIONS:
        action = "none"
    conf = item.get("confidence", "low")
    if conf not in ("high", "medium", "low"):
        conf = "low"
    return {
        "article_id": article_id,
        "relevant": bool(item.get("relevant", False)),
        "stance": stance,
        "themes": themes,
        "action": action,
        "country": str(item.get("country", ""))[:80],
        "locality": str(item.get("locality", ""))[:120],
        "confidence": conf,
    }


def classify_batch(client: anthropic.Anthropic, batch: list[tuple]) -> list[dict]:
    """batch: list of (article_id, title, domain). Returns validated rows."""
    lines = [f'{i + 1}. [{domain}] "{title}"'
             for i, (_id, title, domain) in enumerate(batch)]
    prompt = (
        f"Label these {len(batch)} headlines. Return a JSON array with exactly "
        f"{len(batch)} objects, ids 1..{len(batch)} in order.\n\n" + "\n".join(lines)
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    items = _extract_json(resp.content[0].text)
    rows = []
    for i, (article_id, _title, _domain) in enumerate(batch):
        # match by declared id when present, else by position
        item = next((x for x in items if x.get("id") == i + 1),
                    items[i] if i < len(items) else {})
        rows.append(_validate(item, article_id))
    return rows


def classify_all(conn, verbose: bool = True) -> int:
    """Classify every unclassified article in the DB. Returns count classified.

    Failed batches are SKIPPED (left unclassified) so they are retried on the
    next run — never stored with invented labels.
    """
    from db import unclassified_articles, save_classifications

    client = _client()
    todo_all = unclassified_articles(conn)
    total = 0
    for i in range(0, len(todo_all), BATCH_SIZE):
        batch = todo_all[i:i + BATCH_SIZE]
        try:
            rows = classify_batch(client, batch)
        except Exception as e:
            print(f"    batch failed ({e}) — retrying once...")
            try:
                rows = classify_batch(client, batch)
            except Exception as e2:
                print(f"    batch failed twice ({e2}) — leaving {len(batch)} "
                      "articles unclassified for the next run.")
                continue
        total += save_classifications(conn, rows, MODEL, RUBRIC_VERSION)
        if verbose:
            print(f"    classified {total}/{len(todo_all)} articles...")
    return total
