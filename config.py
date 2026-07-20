"""Central configuration for the AI Data Centre Coverage Monitor."""

# ---------------------------------------------------------------------------
# GDELT queries
# ---------------------------------------------------------------------------
# Stream A ("broad"): a representative sample of ALL English-language data
# centre coverage. This stream is the honest basis for stance shares —
# we do NOT bias it with opposition keywords.
BROAD_QUERY = '("data center" OR "data centre" OR "datacenter" OR "hyperscale") sourcelang:english'

# Stream B ("conflict"): targeted pull for opposition/adverse-action events.
# Used ONLY for hotspot detection and the adverse-actions timeline,
# never for stance-share statistics (it is deliberately biased).
CONFLICT_QUERY = (
    '("data center" OR "data centre" OR "datacenter") '
    '(protest OR moratorium OR lawsuit OR opposition OR opposed OR rezoning '
    'OR "zoning board" OR blocked OR rejected OR backlash OR "water use" '
    'OR "power grid" OR noise) sourcelang:english'
)

# Records to sample per period
BROAD_MAX_RECORDS = 250      # GDELT hard cap per call
CONFLICT_MAX_RECORDS = 100

# Historical baseline start (inclusive), YYYY-MM
BACKFILL_START = "2023-01"

# ---------------------------------------------------------------------------
# GDELT etiquette — free DOC API allows ~1 request per 5 seconds.
# Hammering it triggers a 429 penalty box. Do not lower this.
# ---------------------------------------------------------------------------
GDELT_SLEEP_SECONDS = 6
GDELT_MAX_RETRIES = 4

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
MODEL = "claude-haiku-4-5-20251001"   # cheap + fast; right tool for bulk labelling
RUBRIC_VERSION = "dc-1.0"
BATCH_SIZE = 25                        # headlines per Claude call

STANCES = ["opposed", "supportive", "neutral"]

THEMES = [
    "community_opposition",   # residents / local groups pushing back
    "power_grid",             # electricity demand, grid strain, energy prices
    "water",                  # water consumption, drought concerns
    "environment",            # emissions, climate, land/habitat impact
    "land_zoning",            # rezoning fights, land use, planning permission
    "tax_incentives",         # subsidies, tax breaks (and criticism of them)
    "jobs_investment",        # economic development framing
    "noise_quality_of_life",  # noise, traffic, visual impact
    "regulation_policy",      # laws, moratoria, government policy
    "ai_demand",              # AI boom driving buildout
    "other",
]

ACTIONS = [
    "none",
    "moratorium",             # formal pause/ban enacted or proposed
    "project_blocked",        # permit denied / rezoning refused
    "project_cancelled",      # developer withdrew or scrapped project
    "lawsuit",                # legal challenge filed
    "protest",                # demonstration / organised campaign
    "policy_restriction",     # new law/rule restricting data centres
    "project_approved",       # permit granted / project greenlit
    "project_announced",      # new project or investment announced
]

DB_PATH = "coverage.db"
