# Phase 3 — Decision Engine V1

## Context

Phase 2.5 (Native Planning Surface) shipped on 2026-04-30. The
operator can now edit, branch, save, project, commit, and publish
plans entirely in the dashboard. Phase 3 is the first phase that
shifts from "managing the data" to "answering the question."

**Roadmap goal**: make the app better at answering *what changed*
and *what needs attention now*.

**Roadmap exit criteria** (`docs/roadmap.md:88-100`):

- Weekly review reliably identifies spending shifts, overages, and
  outliers.
- The app explains *why* something is risky, not just that it is risky.

The decision-engine substrate is already partly built:

- `AnalyticsService` (`src/finclaide/analytics.py:56-712`) exposes
  `compare_months`, `spending_trends`, `year_end_projection`,
  `detect_anomalies`, `budget_recommendations`, and
  `financial_health_check`.
- `WeeklyReviewService` (`src/finclaide/services.py:797-1139`)
  composes those into a prioritized `weekly()` payload with
  `_variance_severity` + `_priority_key` ranking.
- The Home page (`frontend/src/routes/+page.svelte`) already
  renders the weekly review (3-column "What Changed / Needs
  Attention / Recommended Actions"), an Overage Watch card, the
  Plan-vs-Actual group chart, Annual Funding status, and recent
  transactions.

The substrate is solid; the gaps are in **depth, narrative, and
in-progress visibility**:

| Gap | Detail |
|---|---|
| In-progress month not surfaced | Overage_watch flags *repeat historical* overages. Nothing answers "you're 80% through Groceries with 10 days left." |
| Year-end projection invisible | `year_end_projection` exists in the API but isn't on Home. |
| Anomaly explanations shallow | σ-distance returned but no narrative ("typical $150-$350; this $500 is +3.2σ"). |
| Recommendations not grounded | "Increase Bills/Claude" doesn't expand to show which transactions drove it. |
| No drilldown route | Everything is on Home. Per-category trend pages, variance heatmaps, etc. have nowhere to live. |

This phase closes those in **four slices** delivering the exit
criteria. Slice 1 detailed below; later slices sketched.

## Phase 3 slicing — 4 slices

### Slice 1 — In-progress month pace + year-end forecast on Home

Highest-leverage first. Adds a "Mid-month pace" card answering
"what's at risk this month" and surfaces the already-existing
`year_end_projection` as a "Year-end forecast" card. Reuses
existing analytics. ~300 LOC + ~11 test cases. Single commit.

**Closes the "what needs attention now" half of the exit criteria.**

### Slice 2 — Anomaly explanations + narratives

Enriches `detect_anomalies` to return typical-range bounds, peer
comparison, and a narrative-ready payload. Frontend renders human
copy: `"Bills/Claude: $500 this month is +3.2σ above the typical
range ($150-$350). Last 6 months averaged $200."` ~250 LOC + ~8
test cases.

**Closes the "explains *why* something is risky" half.**

### Slice 3 — `/insights` route + per-category trend pages

New top-level route hosting deeper drilldowns: per-category trend
page (sparkline → full timeline + anomaly markers), 12-month
variance heatmap, anomaly-by-anomaly drill-in pages, weekly review
archive (snapshot of past weeks). ~500 LOC + ~12 test cases.
**Two commits**: route shell + trend page (3a), heatmap + archive (3b).

### Slice 4 — Recommendation grounding (transaction-level evidence)

Each `budget_recommendations` item gains a `supporting_transactions`
field referencing the specific txns + months that drove it. UI
expands recommendations inline to show that evidence. ~200 LOC +
~5 test cases.

**Order rationale**: Slice 1 is the highest-leverage decision-
making win. Slice 2 builds the explanation layer that Slice 3 can
deep-link into. Slice 4 is the finishing touch and can land any
time.

---

# Slice 1 — In-progress month pace + year-end forecast

## Context (Slice 1)

Today the operator opens Home mid-month and sees: weekly review
(historical-leaning), overage watch (historical pattern), group
chart (current month-to-date totals). What they don't see: which
specific monthly categories are spending faster than the days-elapsed
budget allows, and which annual targets are projected to bust by
year-end.

This slice adds two cards to Home, both backed by existing transaction
data:

1. **Mid-month pace** — ranks current-month monthly + stipends
   categories by projected overage. Shows pace factor + status
   chip + projected month-end value.
2. **Year-end forecast** — surfaces `AnalyticsService.year_end_projection`
   with the top-3 categories projected to exceed their annual target.
   Already computed in the backend; just not on Home.

## Locked design decisions

- **One commit, one PR.** ~300 LOC. Slice fits cleanly in a single
  PR.
- **Pace = `(actual / planned) / (days_elapsed / total_days_in_month)`.**
  Pace > 1.0 means spending faster than the linear-pace budget.
  Pace < 1.0 means under-budget so far.
- **Status thresholds**:

  | Pace factor | Status | Color |
  |---|---|---|
  | actual = 0 | `no_spend_yet` | muted |
  | planned = 0, actual > 0 | `unplanned` | rose |
  | < 0.85 | `under_pace` | emerald |
  | 0.85 ≤ pace ≤ 1.15 | `on_pace` | muted |
  | 1.15 < pace ≤ 1.50 | `over_pace` | amber |
  | 1.50 < pace ≤ 2.00 | `at_risk` | rose-200 |
  | > 2.00 | `blowout` | rose-400 |

- **Eligible blocks**: `monthly` and `stipends` only. Annual,
  one-time, and savings don't have a meaningful month-pace
  (planned amount is annual or one-shot).
- **Surface filter**: only show categories where
  `projected_overage_milliunits > 25_000` (>$25). Tiny categories
  generate noise.
- **Early-month suppression**: if `days_elapsed < 3`, the pace card
  shows "Pace data warming up — at least 3 days of activity needed"
  instead of the table. Single-day extrapolation is too noisy.
- **Year-end forecast** uses the existing `year_end_projection`
  return shape; no new service method, just a new endpoint mirror
  on the UI API and a frontend card.
- **Sort**: pace card sorts by `projected_overage_milliunits desc`,
  showing the worst 5 by default with an "Show all N" expand.
- **Both cards live on Home**, between the weekly review and the
  group chart. They render independently — if pace data isn't
  ready (early month), the year-end card still shows.

## Schema delta

**None.** Both cards read existing transactions + plan_categories.

---

## Backend

### `AnalyticsService.month_pace(month)` — NEW (`src/finclaide/analytics.py`)

```python
def month_pace(
    self,
    *,
    month: str | None = None,
    plan_year: int | None = None,
) -> dict[str, Any]:
    """Per-category mid-month pace analysis for the given month
    (defaults to current). Returns:

    {
      "month": "YYYY-MM",
      "days_elapsed": int,
      "days_total": int,
      "days_remaining": int,
      "warming_up": bool,                 # True if days_elapsed < 3
      "categories": [
        {
          "category_id": int,
          "group_name": str, "category_name": str,
          "block": "monthly" | "stipends",
          "planned_milliunits": int,
          "actual_milliunits": int,
          "pace_factor": float,           # actual/planned ÷ elapsed/total
          "pace_status": "on_pace" | "over_pace" | "at_risk" | ...,
          "projected_month_end_milliunits": int,
          "projected_overage_milliunits": int,
        }, ...
      ],
      "totals": {
        "planned_milliunits": int,
        "actual_milliunits": int,
        "projected_month_end_milliunits": int,
      },
    }
    """
```

Implementation:
- Default `month` to first day of current UTC month via
  `_month_reference(None)`.
- `days_total = calendar.monthrange(year, month)[1]`.
- `days_elapsed = min(today.day, days_total)` (clamp for past months —
  if `month` is in the past, use full month).
- For each `plan_categories` row in active plan with `block ∈
  {'monthly', 'stipends'}`:
  - Sum negative-amount transactions in `[YYYY-MM-01, YYYY-MM+1-01)`
    matching `(group_name, category_name)` (same join as the
    `_category_monthly_spend` helper used by `compare_scenario`).
  - Compute `pace_factor`, `pace_status`, `projected_month_end`,
    `projected_overage`.
- Sort by `projected_overage_milliunits desc`.
- Build `totals` from sums.

Edge cases:
- `planned = 0 AND actual > 0` → `pace_status = "unplanned"`,
  `pace_factor = float('inf')` (frontend handles None/Infinity).
  Use a sentinel like -1.0 in the JSON; frontend treats < 0 as
  "n/a".
- `planned > 0 AND actual = 0` → `pace_status = "no_spend_yet"`,
  `pace_factor = 0.0`.
- `days_elapsed = 0` → return `warming_up=True`, `categories=[]`.

### Endpoints

- `GET /api/analytics/pace?month=YYYY-MM` (private API). Bearer auth.
  Returns the dict above.
- `GET /ui-api/analytics/pace?month=YYYY-MM` (UI mirror).
  Same-origin guard.
- `GET /ui-api/analytics/projection?month=YYYY-MM` (UI mirror of
  the existing `/api/analytics/projection` endpoint, which currently
  has no UI mirror — needed for the year-end card).

### Tests — backend

**`tests/test_analytics.py`** — extend with 6 cases:

- `test_month_pace_returns_warming_up_when_days_elapsed_under_3` —
  freeze "now" to 2026-04-02 (day 2), expect `warming_up=True`,
  `categories=[]`.
- `test_month_pace_computes_pace_factor_and_status` — seed
  Groceries planned $1000, day 15 of 30, $700 spent → pace_factor =
  (700/1000) / (15/30) = 1.4 → status `over_pace`. Projected
  month-end = $1400.
- `test_month_pace_includes_only_monthly_and_stipends_blocks` —
  seed annual/one-time/savings categories, assert excluded.
- `test_month_pace_filters_categories_below_overage_threshold` —
  small projected overage (< $25) excluded from `categories`.
- `test_month_pace_handles_unplanned_category_with_actual_spend` —
  planned=0, actual=$50 on day 10 → status=`unplanned`,
  `pace_factor=-1.0`.
- `test_month_pace_handles_past_month_uses_full_month` — request
  a past month → `days_elapsed = days_total`, pace based on
  realized actuals.

**`tests/test_api.py`** — extend with 2 endpoint cases:

- `test_pace_endpoint_returns_payload` — round-trip 200 with the
  expected shape.
- `test_ui_api_pace_endpoint_mirrors_api`.

---

## Frontend

### API client (`frontend/src/lib/api.ts`)

```ts
export const PaceCategorySchema = z.object({
  category_id: z.number(),
  group_name: z.string(),
  category_name: z.string(),
  block: z.enum(['monthly', 'stipends']),
  planned_milliunits: z.number(),
  actual_milliunits: z.number(),
  pace_factor: z.number(),  // -1.0 sentinel for unplanned
  pace_status: z.enum([
    'no_spend_yet', 'unplanned', 'under_pace', 'on_pace',
    'over_pace', 'at_risk', 'blowout',
  ]),
  projected_month_end_milliunits: z.number(),
  projected_overage_milliunits: z.number(),
})

export const MonthPaceSchema = z.object({
  month: z.string(),
  days_elapsed: z.number(),
  days_total: z.number(),
  days_remaining: z.number(),
  warming_up: z.boolean(),
  categories: z.array(PaceCategorySchema),
  totals: z.object({
    planned_milliunits: z.number(),
    actual_milliunits: z.number(),
    projected_month_end_milliunits: z.number(),
  }),
})

export async function getMonthPace(month?: string) {
  const search = month ? `?month=${month}` : ''
  return requestJson(
    withBasePath(`/ui-api/analytics/pace${search}`),
    MonthPaceSchema,
  )
}
```

Plus `YearEndProjectionSchema` + `getYearEndProjection(month)` —
mirror the existing analytics_api shape.

### Components

- **NEW `frontend/src/components/month-pace-card.svelte`** — ~120
  LOC. Card with title "Mid-month pace · {month_label}". Body:
  - Header row: `Day {N} of {T} · {N} days remaining`.
  - If `warming_up`: muted message "Pace data warming up — at
    least 3 days of activity needed."
  - Otherwise: table with Category, Planned, Spent, Pace, Projected
    overage. Status chip per row.
  - Footer: "Show all N" if more than 5 categories.
- **NEW `frontend/src/components/year-end-forecast-card.svelte`** —
  ~80 LOC. Card with title "Year-end forecast." Body: top-3
  projected-variance categories sorted desc. Each row: category
  name, planned annual, projected annual, variance with up/down
  arrow.

### Home wiring (`frontend/src/routes/+page.svelte`)

Add two `createQuery` calls (one per card), mount the cards
between the weekly review section and the existing group chart.
Both queries gated by `enabled: browser` (matching existing
pattern).

### Frontend tests

**`frontend/src/components/month-pace-card.test.ts` (NEW)** — 3 cases:
- renders warming-up state
- renders pace table with status chips
- "Show all" expands beyond 5 rows

**`frontend/src/components/year-end-forecast-card.test.ts` (NEW)** —
2 cases:
- renders top-3 categories sorted by variance
- renders empty state when no projected overages

Total: +5 vitest cases.

## Pass gate (Slice 1)

- `make test` green. pytest grows by 8 cases.
- `cd frontend && npm run check` 0/0; `npx vitest run` green
  (+5 cases).
- Manual smoke against docker stack:
  - Open Home in early April → "Mid-month pace" shows warming-up
    message.
  - Open Home mid-April → table populated; click "Show all";
    Groceries row shows realistic pace + projected overage.
  - Year-end forecast card shows top-3 categories projected over
    their annual target.
  - Empty state if all categories on track.
- Commit: `Add Phase 3 Slice 1: month pace + year-end forecast on Home`.

## Critical files (Slice 1)

Backend:
- `src/finclaide/analytics.py` — add `month_pace()` method.
- `src/finclaide/analytics_api.py` — `GET /analytics/pace`
  endpoint.
- `src/finclaide/ui_api.py` — UI mirrors for `/analytics/pace`
  and `/analytics/projection`.
- `tests/test_analytics.py` — +6 cases.
- `tests/test_api.py` — +2 cases.

Frontend:
- `frontend/src/lib/api.ts` — `getMonthPace`,
  `getYearEndProjection`, schemas.
- `frontend/src/components/month-pace-card.svelte` (NEW).
- `frontend/src/components/year-end-forecast-card.svelte` (NEW).
- `frontend/src/components/month-pace-card.test.ts` (NEW).
- `frontend/src/components/year-end-forecast-card.test.ts` (NEW).
- `frontend/src/routes/+page.svelte` — mount the two new cards.

---

# Slices 2-4 — sketches (filled in when their turn comes)

## Slice 2 — Anomaly explanations

**Service**: extend `detect_anomalies` to attach a `narrative`
field per anomaly:

```python
{
  "narrative": {
    "typical_low_milliunits": int,
    "typical_high_milliunits": int,
    "n_month_average_milliunits": int,
    "headline": "$500 is +3.2σ above the typical $150-$350 range.",
    "context": "Last 6 months averaged $200.",
    "peer_categories": [{"name": "Bills/T-Mobile", "delta_pct": 12.5}],
  },
}
```

**Frontend**: each anomaly in the weekly review's "Needs Attention"
column renders the headline; clicking expands to show context +
peer comparison. Reuses `compare-drawer` patterns.

**Pass gate**: a real anomaly on the operator's data shows a
narrative that reads naturally.

## Slice 3 — `/insights` route

**Routes**:
- `/insights` — landing page with per-category trend grid
  (sparkline-per-row + status chip from Slice 1).
- `/insights/categories/:id` — full timeline for one category, with
  anomaly markers and the related transactions.
- `/insights/heatmap` — 12-month × N-categories color-coded
  variance grid.
- `/insights/archive` — past weekly review snapshots.

Two commits: route shell + trend page (3a), heatmap + archive (3b).

**Pass gate**: operator can drill from a Home anomaly into the
specific transactions over the last 6 months, then jump to the
relevant category's trend.

## Slice 4 — Recommendation grounding

**Service**: extend `budget_recommendations` to attach a
`supporting_evidence` field:

```python
{
  "supporting_evidence": {
    "recent_overage_months": ["2026-01", "2026-02", "2026-03"],
    "overage_milliunits_by_month": {...},
    "top_transactions": [{tx_id, date, payee, amount}, ...],
  },
}
```

**Frontend**: expandable per-recommendation panel showing the
months + transactions driving the suggestion.

**Pass gate**: the recommendation row, when expanded, shows the 3-5
transactions the operator should look at to validate the
suggestion.

---

## Phase 3 verification (after all 4 slices)

End-to-end smoke covering: Home load → see 5 new cards (slice 1+2);
click anomaly → narrative expands (slice 2); click "more" → land on
`/insights/categories/:id` (slice 3); click recommendation → see
supporting transactions (slice 4). Each slice has its own pytest +
vitest coverage.

## Out of scope for Phase 3

- ML-driven anomaly classification (rule-based σ + payee history
  only in v1).
- Push notifications / alerts. Decision engine surfaces in the UI;
  no email/Slack/webhook in v1.
- "What if I cut Groceries by 15%?" interactive sliders on
  /insights — that's Phase 2.5c projection territory.
- Cross-year forecasting (Phase 4 — Cash Flow & Forecasting).
- Goal pressure / sinking fund recommendations (Phase 5 — Goals
  & Savings Planning).
- AI-narrative generation (Phase 8 — Human-Led AI Copilot).
