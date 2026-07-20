"""AI Data Centre Coverage Monitor — Streamlit dashboard.

Reads coverage.db and tells the story of how public and political attitudes
toward data centre development are shifting. Every chart is backed by real,
clickable headlines.

Run with:  uv run streamlit run dashboard.py
"""

import json
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import DB_PATH, THEMES

st.set_page_config(page_title="AI Data Centre Coverage Monitor",
                   page_icon="🏭", layout="wide")

ADVERSE_ACTIONS = ["moratorium", "project_blocked", "project_cancelled",
                   "lawsuit", "protest", "policy_restriction"]
STANCE_COLORS = {"opposed": "#d62728", "neutral": "#9e9e9e", "supportive": "#2ca02c"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """SELECT a.id, a.url, a.title, a.domain, a.seen_date, a.month, a.stream,
                  c.relevant, c.stance, c.themes, c.action, c.country,
                  c.locality, c.confidence
           FROM articles a JOIN classifications c ON c.article_id = a.id""",
        conn,
    )
    tl = pd.read_sql_query("SELECT series, date, value FROM timelines", conn)
    conn.close()
    df["themes"] = df["themes"].apply(lambda s: json.loads(s) if s else [])
    return df, tl


try:
    df, tl = load_data()
except Exception:
    st.error("No data found — run the backfill first: `uv run backfill.py`")
    st.stop()

if df.empty:
    st.error("Database is empty — run the backfill first: `uv run backfill.py`")
    st.stop()

rel = df[df["relevant"] == 1].copy()
# Stance statistics come from the fixed outlet panel (NYT + Guardian) — a
# consistent measuring instrument across the whole window. Fall back to the
# NewsAPI broad sample only if the panel backfill hasn't run yet.
panel = rel[rel["stream"] == "panel"]
trend = panel if len(panel) else rel[rel["stream"] == "broad"]
months = sorted(rel["month"].unique())

# ---------------------------------------------------------------------------
# Header + headline metrics
# ---------------------------------------------------------------------------
st.title("AI Data Centre Coverage Monitor")
st.caption(
    "How public and political attitudes toward data centre development are "
    "shifting — measured from classified public news coverage, "
    f"{months[0]} to {months[-1]}. Built for the Credit & Political Risks desk. "
    "Public sources only; every figure drills down to its headlines."
)

def opp_share(frame) -> float:
    return 100 * (frame["stance"] == "opposed").mean() if len(frame) else 0.0

recent_months = months[-3:]
baseline_months = [m for m in months if m.startswith("2023")] or months[:3]
recent_share = opp_share(trend[trend["month"].isin(recent_months)])
baseline_share = opp_share(trend[trend["month"].isin(baseline_months)])
recent_adverse = rel[(rel["month"].isin(recent_months)) & (rel["action"].isin(ADVERSE_ACTIONS))]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Articles classified", f"{len(df):,}")
c2.metric("Oppositional share (last 3 mo)", f"{recent_share:.0f}%",
          delta=f"{recent_share - baseline_share:+.0f} pts vs 2023",
          delta_color="inverse")
c3.metric("Adverse actions (last 3 mo)", len(recent_adverse),
          help="Moratoria, blocked/cancelled projects, lawsuits, protests, restrictions")
top_theme = (trend[trend["stance"] == "opposed"].explode("themes")["themes"]
             .value_counts().index)
c4.metric("Top opposition theme", (top_theme[0] if len(top_theme) else "—").replace("_", " "))

st.divider()

# ---------------------------------------------------------------------------
# 1. The story: stance shares over time
# ---------------------------------------------------------------------------
st.subheader("The story: stance of coverage over time")
st.caption("Share of relevant coverage each month, measured on a fixed panel "
           "of two quality outlets (NYT + Guardian) — the same instrument "
           "across the whole window, so months are comparable.")

# counts per month x stance, smoothed over a 3-month window so thin early
# months (a handful of articles) don't produce jagged noise
counts = (trend.groupby(["month", "stance"]).size().unstack(fill_value=0)
          .reindex(columns=["opposed", "neutral", "supportive"], fill_value=0)
          .sort_index().rolling(3, min_periods=1).mean())
shares = counts.div(counts.sum(axis=1), axis=0).mul(100).reset_index()
stance_m = shares.melt(id_vars="month", var_name="stance", value_name="share")
fig = px.area(stance_m, x="month", y="share", color="stance",
              color_discrete_map=STANCE_COLORS,
              category_orders={"stance": ["opposed", "neutral", "supportive"]},
              labels={"share": "% of coverage", "month": ""})
fig.update_layout(height=380, legend_title_text="", margin=dict(t=10))
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Independent check: GDELT volume & tone (no LLM involved)
# ---------------------------------------------------------------------------
if not tl.empty:
    st.subheader("Independent check: coverage volume & tone (GDELT)")
    st.caption("GDELT's own aggregates over ALL matching coverage — an "
               "objective reference series with no LLM in the loop.")
    vol = tl[tl["series"] == "volume"].sort_values("date")
    tone = tl[tl["series"] == "tone"].sort_values("date")
    fig2 = go.Figure()
    if not vol.empty:
        v = vol.set_index("date")["value"].rolling(14, min_periods=1).mean()
        fig2.add_trace(go.Scatter(x=v.index, y=v.values, name="Volume (% of all news, 14d avg)",
                                  line=dict(color="#1f77b4")))
    if not tone.empty:
        t = tone.set_index("date")["value"].rolling(14, min_periods=1).mean()
        fig2.add_trace(go.Scatter(x=t.index, y=t.values, name="Avg tone (14d avg)",
                                  line=dict(color="#ff7f0e"), yaxis="y2"))
    fig2.update_layout(
        height=340, margin=dict(t=10),
        yaxis=dict(title="Volume"),
        yaxis2=dict(title="Tone (neg ↓)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# 3. What the opposition is about: themes over time
# ---------------------------------------------------------------------------
st.subheader("What the opposition is about")
st.caption("Themes present in oppositional coverage, by month.")
opp = trend[trend["stance"] == "opposed"].explode("themes").dropna(subset=["themes"])
if not opp.empty:
    theme_m = opp.groupby(["month", "themes"]).size().rename("n").reset_index()
    fig3 = px.bar(theme_m, x="month", y="n", color="themes",
                  labels={"n": "oppositional articles", "month": ""})
    fig3.update_layout(height=380, legend_title_text="", margin=dict(t=10))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No oppositional coverage classified yet.")

# ---------------------------------------------------------------------------
# 4. Hotspots + adverse actions
# ---------------------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Hotspots")
    period = st.selectbox("Period", ["Last 3 months", "Last 6 months", "Last 12 months", "All time"])
    n_map = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All time": len(months)}
    sel_months = months[-n_map[period]:]
    hot = rel[(rel["month"].isin(sel_months)) &
              ((rel["stance"] == "opposed") | (rel["action"].isin(ADVERSE_ACTIONS)))]
    by_loc = (hot[hot["locality"] != ""].groupby(["country", "locality"]).size()
              .rename("articles").reset_index().sort_values("articles", ascending=False))
    st.caption("Localities ranked by oppositional coverage + adverse actions. "
               "Hotspots emerge from the data — no fixed watchlist.")
    st.dataframe(by_loc.head(20), use_container_width=True, hide_index=True)

with right:
    st.subheader("Concrete adverse actions")
    st.caption("Moratoria, blocked/cancelled projects, lawsuits, protests, restrictions.")
    adverse = rel[rel["action"].isin(ADVERSE_ACTIONS)].sort_values("seen_date", ascending=False)
    show = adverse[["seen_date", "action", "locality", "country", "title", "url"]].head(50)
    st.dataframe(
        show, use_container_width=True, hide_index=True, height=420,
        column_config={
            "url": st.column_config.LinkColumn("link", display_text="open"),
            "seen_date": "date",
        },
    )

# ---------------------------------------------------------------------------
# 5. Headline explorer
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Headline explorer")
f1, f2, f3, f4 = st.columns(4)
sel_stance = f1.multiselect("Stance", ["opposed", "neutral", "supportive"])
sel_theme = f2.multiselect("Theme", THEMES)
sel_country = f3.multiselect("Country", sorted(rel.loc[rel["country"] != "", "country"].unique()))
search = f4.text_input("Search headlines")

ex = rel.copy()
if sel_stance:
    ex = ex[ex["stance"].isin(sel_stance)]
if sel_theme:
    ex = ex[ex["themes"].apply(lambda ts: any(t in ts for t in sel_theme))]
if sel_country:
    ex = ex[ex["country"].isin(sel_country)]
if search:
    ex = ex[ex["title"].str.contains(search, case=False, na=False)]

st.caption(f"{len(ex):,} articles match.")
st.dataframe(
    ex[["seen_date", "stance", "action", "country", "locality", "title", "url"]]
    .sort_values("seen_date", ascending=False).head(500),
    use_container_width=True, hide_index=True, height=420,
    column_config={
        "url": st.column_config.LinkColumn("link", display_text="open"),
        "seen_date": "date",
    },
)

# ---------------------------------------------------------------------------
# Methodology — honesty is the credibility
# ---------------------------------------------------------------------------
with st.expander("Methodology & limitations"):
    st.markdown("""
**What this is.** A first-pass triage monitor of public news coverage of data
centre development, built for underwriting discussion. It measures *coverage*,
which is a proxy for public and political attitudes — not a direct poll.

**How it works.** Claude Haiku labels each headline against a fixed rubric
(stance, themes, concrete actions, geography, confidence) at temperature 0.
Counts of those labels — not model opinion scores — produce every figure above.

**Two layers.** The stance trend is measured on a fixed *panel* of two quality
outlets (New York Times + The Guardian): their complete data centre coverage,
Jan 2023 → today, the same instrument in every month, so months are genuinely
comparable. A separate *breadth* layer (NewsAPI, ~150k outlets, daily since
Jul 2026) widens the net for hotspots, adverse events, and the headline
explorer, but is never mixed into the panel trend statistics.

**Limitations.** Headline-only classification; English-language sources; the
panel is two Western outlets (strong on the US and UK/Europe flashpoints,
thinner on local and non-Western press — the breadth layer partly compensates
from Jul 2026 onward); media coverage may lead or lag actual permitting
outcomes; no internal, exposure, or policy data is used anywhere.
Classification model and rubric version are stored with every label for
auditability.
    """)
