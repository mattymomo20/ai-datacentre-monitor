# AI Data Centre Coverage Monitor

A first-pass triage tool for a credit & political risks underwriting desk:
it measures how public and political attitudes toward **AI data centre
development** are shifting, using classified public news coverage from
January 2023 to today.

## Why

The desk has been declining data centre projects as public perception turns.
This tool puts numbers and evidence behind that turn: how fast is opposition
growing, what is it about (water, power, zoning, tax breaks), where is it
concentrated, and which concrete adverse actions (moratoria, blocked projects,
lawsuits) have actually happened.

## How it works — measurement, not opinion

1. **Ingest.** GDELT's DOC API supplies a monthly (historical) and daily
   (ongoing) sample of global English-language data centre news. Two streams:
   a *broad* unbiased sample for statistics, and a targeted *conflict* stream
   used only to catch adverse events.
2. **Classify.** Claude Haiku labels every headline against a fixed rubric
   (`classification_rubric.md`): relevance, stance (opposed / supportive /
   neutral), themes, concrete actions, geography, confidence. Temperature 0;
   model + rubric version stored with every label.
3. **Count.** Every chart is an aggregation of those labels — the tool never
   asks the model for an opinion score. Every figure drills down to the actual
   headlines behind it.
4. **Cross-check.** GDELT's own volume and tone timelines (no LLM involved)
   are shown alongside as an independent reference.

Public news only — no internal, exposure, or policy data anywhere.

## Running it

```bash
uv sync                                # install dependencies
uv run backfill.py                     # one-off: build the 2023->now baseline (~1 hr)
uv run streamlit run dashboard.py      # dashboard at localhost:8501
uv run daily.py                        # manual daily update (the Action does this)
```

Requires a `.env` file with `ANTHROPIC_API_KEY=...` (gitignored). The GitHub
Action (`.github/workflows/daily.yml`) runs `daily.py` at 06:00 UTC and
commits the updated `coverage.db`.

## Files

| File | Purpose |
|---|---|
| `config.py` | Queries, fixed label sets, model, constants |
| `classification_rubric.md` | The labelling rubric fed to the model |
| `gdelt.py` | Rate-limited GDELT client (respects 1 req/6s) |
| `classify.py` | Batched Haiku classification with validation |
| `db.py` | SQLite schema and helpers |
| `backfill.py` | Resumable historical backfill (Jan 2023 →) |
| `daily.py` | Daily incremental run |
| `dashboard.py` | Streamlit dashboard |
| `coverage.db` | SQLite store (committed so the cloud dashboard has data) |

## Limitations (by design, stated openly)

Headline-only classification; English-language coverage; up to 250 broad
articles sampled per month (GDELT cap); media coverage is a proxy for
attitudes, not a poll; coverage may lead or lag permitting outcomes.
