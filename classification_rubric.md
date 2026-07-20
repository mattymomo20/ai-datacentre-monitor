# Classification rubric — AI Data Centre Coverage Monitor (v dc-1.0)

You are labelling news headlines for a credit & political risks underwriting desk
that insures data centre projects. The desk needs to measure how public and
political attitudes toward data centre development are shifting. Label each
headline exactly as instructed. Base every label ONLY on the headline text and
source domain given — do not invent facts.

## Fields

### relevant (true/false)
`true` if the article is substantively about data centre **facilities, projects,
or the data centre industry**: siting, construction, expansion, operations,
energy or water use, community relations, regulation, incentives, investment,
opposition, or policy.

`false` if "data center"/"data centre" is incidental: cloud product launches,
software news, service outages, earnings coverage where facilities are not the
story, job listings, or unrelated uses of the phrase.

### stance (opposed / supportive / neutral)
The article's overall framing toward **data centre development/expansion**:

- `opposed` — foregrounds harms, resistance, or restriction: community backlash,
  environmental damage, grid strain, water depletion, blocked or cancelled
  projects, critical investigations, calls for moratoria.
- `supportive` — foregrounds benefits or momentum: investment, jobs, economic
  growth, approvals, expansion framed positively, favourable incentives.
- `neutral` — factual, balanced, or mixed reporting without clear framing either way.

Judge the framing of the coverage, not your own view. If genuinely unclear from
the headline, use `neutral` with `confidence: low`.

### themes (list, max 3, from the fixed set)
`community_opposition`, `power_grid`, `water`, `environment`, `land_zoning`,
`tax_incentives`, `jobs_investment`, `noise_quality_of_life`,
`regulation_policy`, `ai_demand`, `other`

### action (one of the fixed set)
A **concrete event** reported in the headline, not mere sentiment:

- `moratorium` — a formal pause or ban enacted or formally proposed
- `project_blocked` — permit denied, rezoning refused
- `project_cancelled` — developer withdrew or scrapped a project
- `lawsuit` — legal challenge filed
- `protest` — demonstration or organised campaign
- `policy_restriction` — new law/rule restricting data centres
- `project_approved` — permit granted, project greenlit
- `project_announced` — new project or investment announced
- `none` — no concrete event, just commentary/analysis

### country / locality
Country name in English (e.g. "United States", "Ireland"), and the most specific
locality mentioned (e.g. "Loudoun County, Virginia", "Dublin"). Empty string if
not determinable from the headline. Never guess a geography that isn't indicated.

### confidence (high / medium / low)
How certain the labels are given only a headline. Short or ambiguous headlines
must be `low`. Honest low confidence is preferred over invented certainty.

## Output format
Return ONLY a JSON array, one object per headline, in the same order, e.g.:

```json
[
  {"id": 1, "relevant": true, "stance": "opposed", "themes": ["water", "community_opposition"],
   "action": "moratorium", "country": "United States", "locality": "Tucson, Arizona",
   "confidence": "high"}
]
```

If `relevant` is false, still fill the other fields with `"neutral"`, `[]`,
`"none"`, `""`, `""`, and your confidence that it is irrelevant.
