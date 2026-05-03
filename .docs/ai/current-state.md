# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main` — `svelte-migration` fast-forwarded in on 2026-04-24 (tip
`b39b0ed`). Branch `svelte-migration` still exists locally and is
identical to `main`; safe to delete once origin is pushed.

## Last Session Summary

**Date**: 2026-05-03 (Phase 2.5f — Self-service reconcile)

The Reconcile Preview card on Operations turned actionable. Today's earlier
session forced me to drive ~22 manual API calls to fix a 6-mismatch reconcile
failure (8 renames + 1 delete + 13 adds). This slice makes that one-click.

**Backend** (`src/finclaide/services.py`):
- New `_normalize_for_match(name)` helper: collapses whitespace incl. NBSP
  (U+00A0), drops unicode replacement chars (U+FFFD), lowercases. Used only
  for similarity scoring; the plan keeps YNAB's exact bytes.
- New `_score_match(plan_group, plan_name, ynab_group, ynab_name)` helper:
  `difflib.SequenceMatcher.ratio()` on normalized names + 0.10 same-group
  bonus.
- `ReconciliationService.preview()` extended: each `extra_in_ynab` and
  `missing_in_ynab` item now carries an optional `suggested_match` field
  (group_name, category_name, confidence, plan_category_id). Threshold for
  "show a suggestion" = 0.75. `extra_in_ynab` suggestions point at the
  plan-side row (with plan_category_id set so the frontend can PATCH
  directly); `missing_in_ynab` suggestions point at the YNAB-side name.

**Frontend** (`frontend/src/`):
- `lib/api.ts`: `ReconcileSuggestionSchema` added, wired into
  `ReconcilePreviewEntrySchema` as `suggested_match`.
- `components/reconcile-preview-card.svelte` (rewritten): replaces the
  read-only diff lists with action-bearing rows. Each `extra_in_ynab` row
  shows "Rename" (when there's a confident plan-side match) + "Add to
  plan" buttons. Each `missing_in_ynab` row shows "Delete from plan"; if
  the row is already covered by an `extra_in_ynab` rename suggestion,
  it's hidden so the operator only makes one decision per pair.
  Destructive delete prompts a confirm modal when `planned_milliunits > 0`.
- `routes/operations/+page.svelte`: passes the active plan into the card
  so it can resolve `plan_category_id → block + planned_milliunits`
  without a second roundtrip.

**Tests added**:
- `tests/test_reconciliation_suggestions.py` (NEW) — 8 cases covering
  normalization, same-group bonus, no-suggestion when in sync, high-
  confidence rename, NBSP + replacement-char handling, low-confidence
  null suggestion, missing_in_ynab suggestion direction, endpoint
  round-trip.
- `frontend/src/components/reconcile-preview-card.test.ts` (NEW) — 6
  cases covering rename rendering + click, add to plan, delete-when-zero
  (no modal) and delete-when-nonzero (modal).

**Test counts (final)**: pytest **234/234** (was 226; +8). vitest
**382/382** (was 376; +6). svelte-check 0/0.

**Out of scope** (deferred): bulk-apply, group-rename detection, auto-
rename on YNAB sync. The architecture rule (YNAB owns names; operator
confirms each change) stays.

---

**Earlier session**: 2026-05-03 (Phase 2.5e — App as plan source of truth; sheet is one-way artifact)

The scheduled refresh and Refresh All operations were both running
`run_budget_import` first, which clobbered any in-app plan edits and (in
practice) failed the entire refresh whenever the workbook had any
internal inconsistency (e.g. cached SUM formula didn't match the
category sums). Operator surfaced the issue from a real failure: the
April-May 2026 refresh was failing on `expected 1638333, got 1671668`.

The architectural fix codifies what Phase 2.5 was already moving toward:

- **YNAB** owns actuals (transactions, accounts, categories).
- **The application (SQLite)** owns the plan.
- **The Google Sheet / xlsx** is a **one-way artifact** — written by
  Publish-to-Sheets / Export, not read on a schedule.

Backend changes:
- `src/finclaide/scheduled_refresh.py:run_once` no longer calls
  `run_budget_import`. Schedule = sync YNAB + reconcile only.
- `src/finclaide/operations.py:run_refresh_all` matches: sync + reconcile.
- `src/finclaide/ui_api.py:/operations/refresh-all` matches: response
  shape no longer includes `budget_import`.
- The `/api/budget/import` and `/ui-api/operations/import-budget`
  endpoints stay, repurposed as a **manual recovery** path.

Frontend changes:
- Operations page: dropped the "Import Budget" tile. Added "Restore
  from workbook" tile in its place, painted destructive (rose border),
  with copy noting it overwrites the in-app plan. Click opens a
  confirm modal: "Restore plan from workbook?" → Cancel / Restore plan.
- Updated copy on Sync YNAB ("YNAB is the source of truth for actuals"),
  Reconcile ("Verify the in-app plan still matches YNAB category names
  exactly"), and Refresh All ("Sync YNAB then reconcile against the
  in-app plan. Does not re-import the workbook.").

Tests:
- 4 pytest cases updated to pre-seed the plan via explicit budget
  import call now that the schedule no longer does it
  (`test_refresh_all_returns_partial_payload_on_reconcile_failure`,
  `test_scheduled_refresh_run_is_reflected_in_status`,
  `test_scheduled_refresh_failure_is_reflected_in_status`,
  `test_scheduler_bootstraps_when_no_prior_successful_runs`).
- `test_budget_import_sync_reconcile_and_summary` asserts
  `budget_import` is **not** in the refresh-all payload.
- 1 vitest case updated to click "Restore from workbook" then confirm
  via the modal instead of clicking the now-removed "Import Budget"
  button.

**Test counts (final)**: pytest **226/226** (no count change; same
tests, fixed assertions). vitest **376/376** unchanged. svelte-check
0/0.

What this fixes for the operator: the scheduled refresh card on Home
should stop showing "Budget totals do not match cached formulas..."
errors — that error path is no longer in the schedule's path. YNAB
sync + reconcile will run unblocked. The reconcile failure ("6
mismatches" in the screenshot) is now the canonical signal of plan
drift from YNAB; fix it in the in-app planning UI, not by re-importing.

---

**Earlier session**: 2026-04-30 (Phase 3 Slice 1 — Mid-month pace + year-end forecast on Home)

Slice 1 of Phase 3 (Decision Engine V1) shipped in a single commit. Adds two
new home-page cards backed by existing transaction data + a new analytics
service method.

**Backend** (`src/finclaide/analytics.py`, `analytics_api.py`, `ui_api.py`):
- `_classify_pace(planned, actual, days_elapsed, days_total)` module helper —
  returns `(pace_factor, pace_status)` per the spec ladder. Status states:
  `no_spend_yet` / `unplanned` / `under_pace` / `on_pace` / `over_pace` /
  `at_risk` / `blowout`. `pace_factor = (actual/planned) ÷ (days_elapsed/days_total)`;
  -1.0 sentinel for unplanned.
- `AnalyticsService.month_pace(month=None, now=None)` — per-category mid-
  month pace for `monthly` + `stipends` blocks of the active plan. Returns
  `{month, days_elapsed, days_total, days_remaining, warming_up, categories,
  totals}`. Sorts by `projected_overage_milliunits desc`. `warming_up=True`
  when fewer than 3 days elapsed (suppresses noisy single-day extrapolation).
  `now` is overridable for tests.
- New endpoints: `GET /api/analytics/pace?month=YYYY-MM`,
  `GET /ui-api/analytics/pace?month=YYYY-MM`, plus a UI mirror at
  `GET /ui-api/analytics/projection` for the existing year-end-projection
  service method (which previously had no UI mirror).

**Frontend** (`frontend/src/`):
- `lib/api.ts` — `MonthPaceSchema`, `PaceCategorySchema`,
  `YearEndProjectionSchema`, `ProjectionCategorySchema` + types;
  `getMonthPace(month?)` and `getYearEndProjection(month?)` functions.
- `components/month-pace-card.svelte` (NEW) — card showing top-5 surfaced
  categories (sorted by projected overage). Status chip per row with the 7-
  state ladder mapped to color tokens. "Show all N" expand. Surface filter:
  drops categories with projected overage < $25 unless their status is
  unplanned/at_risk/blowout (always surfaced). Renders warming-up message
  for early-month.
- `components/year-end-forecast-card.svelte` (NEW) — top-3 categories
  projected to exceed annual target, sorted by variance desc. Footer line
  shows year-end projected total + variance vs plan. Filter threshold $50
  to keep tiny categories off the card.
- `routes/+page.svelte` — mounts both cards in a 2-col xl grid between the
  weekly review and the existing Plan-vs-Actual group chart. Each card has
  its own `createQuery` keyed by month; both gated by `enabled: browser`.

**Tests added**: 7 `_classify_pace` cases + 6 `month_pace` service cases +
2 endpoint cases (private + UI mirror) = +15 pytest. 3 month-pace-card +
2 year-end-forecast-card vitest cases = +5 vitest.

**Manual smoke deferred** — the cards work end-to-end against the seeded
test fixture in pytest; manual UI smoke against `docker compose up` is the
operator's call. Stack rebuilds needed if you want to see the new cards in
the running browser.

**Test counts (final)**: pytest **223/223** (was 208; +15). vitest
**376/376** (was 371; +5). svelte-check 0/0.

---

**Earlier session**: 2026-04-30 (Phase 2.5d — Publish Plan: xlsx + Sheets write-back)

Phase 2.5d shipped in two commits (5b5ca5d + this commit) closing the
last unmet Phase 2.5 exit criterion ("Sheet exports remain readable by
non-app users and round-trip back into the importer").

**5a — xlsx export** (`src/finclaide/plan_exporter.py`,
`src/finclaide/export_storage.py`, +5 endpoint cases, +6 exporter cases):
- `PlanExporter.export_active_plan()` renders the active plan into a
  fresh `.xlsx` whose column layout mirrors `BudgetImporter` exactly
  (A:B monthly / D:G yearly+one-time / I:J stipends / L:M savings; row
  53 totals with `=SUM` formulas + injected cached values for round-trip
  validation).
- `build_plan_cell_grid(plan) → PlanCellGrid` (cells dict + cached_values
  + row_count) extracted as a layout-aware builder shared with the Sheets
  publisher.
- `ExportStorage` persists rendered bytes under `{db_dir}/exports/{run_id}.xlsx`
  with a 20-file LRU cap.
- `Database.record_run()` now returns `int` (the inserted run id).
- `POST /api/budget/export` + `/ui-api/operations/export-budget` (201
  with `{run_id, filename, row_count, file_size_bytes}`); `GET .../export/<run_id>/download`
  streams bytes with `Content-Disposition: attachment`.
- Operations page: "Export .xlsx" button (5th in the action grid; layout
  shifted from 4-col to 3-col). Run-history label maps to `Export .xlsx`.

**5b — Google Sheets publish** (`src/finclaide/sheets_publisher.py`,
+5 publisher cases, +2 endpoint cases):
- `SheetsPublisher.publish()` creates a new tab in the configured
  workbook (gid via Sheets API `:batchUpdate addSheet`, cells via
  `values:batchUpdate USER_ENTERED`). Tab name template:
  `2026 Budget — published {YYYY-MM-DD HHMM}`. Same-minute collisions
  retry with `(2)`, `(3)` suffixes (10-attempt cap).
- Implementation deviation from spec: uses raw `httpx` instead of
  `google-api-python-client` to match the existing `budget_source.py`
  pattern. Avoids 3 new pip deps; same mocking story as the importer's
  Drive client.
- `_SheetsServiceAccountTokenProvider` mirrors
  `GoogleServiceAccountTokenProvider` from `budget_source.py` but
  requests `https://www.googleapis.com/auth/spreadsheets` scope (write).
- `POST /api/budget/publish` + `/ui-api/operations/publish-budget`
  (201 with `{run_id, tab_name, tab_id, tab_url, spreadsheet_id, row_count}`).
  Wrapped in `operation_lock.guard("budget_publish")`.
- Operations page: "Publish to Sheets" button (6th in grid). Disabled
  unless `status_query.plan_provenance.source_type === 'google_sheets'`
  (extra `forceDisabled` snippet param). Toast on success has an "Open"
  action that opens `tab_url` in a new tab. Run-history label maps to
  `Publish to Sheets`.

**Operator setup gotcha**: Slice 5b requires the operator to re-share
the source workbook with the service-account email as **Editor**. The
existing import flow only needed Viewer. One-time UI action in Drive.

**Test counts (final)**: pytest **208/208** (was 190 pre-2.5d; +13 this
phase = 6 exporter + 5 publisher + 2 publish endpoint cases). vitest
**371/371** (was 369 pre-2.5d; +2 page tests for Publish button enabled/
disabled paths). svelte-check 0/0.

**Manual smoke deferred** — the Google Sheets path needs a real
service-account credential + a configured `FINCLAIDE_GOOGLE_SHEETS_FILE_ID`
to exercise the Drive API end-to-end. The publisher's tests fully cover
the request shape via `httpx.MockTransport`; manual smoke is a follow-up
when the operator has credentials wired.

---

**Earlier session**: 2026-04-30 (Phase 2.5c Slice 4 — projection panel)

Slice 4 (Pure Projection Panel) shipped in two commits (18b9cb8 + eaf655c):

**4a — Backend** (`src/finclaide/plan_service.py`, `src/finclaide/ui_api.py`):
- `compare_projection(axes, new_lines)`: stateless overlay of active plan
  with percent-delta axes + hypothetical new lines. Returns the same shape
  as `compare_scenario` with `scenario_id=None`. Pure read, no writes.
- `apply_projection_to_sandbox(axes, new_lines)`: creates a fresh sandbox
  from the active plan, applies axis overrides via `update_category` (writes
  `ui_update` plan_revisions per category), inserts new hypothetical lines
  via `create_category`. Pre-checks sandbox collision and raises
  `DataIntegrityError` so the UI can show the auto-park modal.
- `/scenarios/compare` endpoint now accepts EITHER `{scenario_id}` (existing
  path) OR `{projection: {axes, new_lines}}` (new path). 400 if both or
  neither.
- `/scenarios/projection/apply-to-sandbox` endpoint (POST, 201), wrapped in
  `operation_lock.guard("plan_apply_projection")`.
- +9 service-level cases in `tests/test_scenarios.py`, +4 endpoint cases in
  `tests/test_scenarios_api.py`. Total pytest: 177 → 190.

**4b — Frontend** (`frontend/src/`):
- `components/ui/slider.svelte`: thin bits-ui Slider wrapper (single-thumb,
  -100% to +100%, step 5%).
- `components/projection-panel.svelte`: sliders for top-8 categories with
  "Show all" expand, add-hypothetical-line form (group autocomplete, category,
  $/mo), debounced 200ms inline summary card (annual delta + top-3 movers),
  "View details" button opens compare-drawer in projection mode, "Apply to
  Sandbox" button with auto-park modal (Cancel/Discard sandbox/Save & apply)
  reusing the same 3-button pattern from `/scenarios`.
- `components/compare-drawer.svelte`: extended with optional `projection` prop;
  `$effect` branches query opts to `compareProjection` when `projection` is
  provided and `scenarioId` is null.
- `routes/scenarios/+page.svelte`: mounts `<ProjectionPanel />` after the
  saved-scenarios card.
- `lib/api.ts`: `ProjectionAxisSchema`, `ProjectionNewLineSchema`,
  `ProjectionRequestSchema` + types; `compareProjection`,
  `applyProjectionToSandbox`; `CompareResponseSchema.scenario_id` made
  nullable.
- +6 vitest cases in `projection-panel.test.ts`, +1 in `compare-drawer.test.ts`.
  Total vitest: 360 → 367. svelte-check: 0/0.

**Implementation note**: In Svelte 5, `$derived` values that are only read
inside async event handlers (not in the template) do not establish reactive
subscriptions with TanStack Query — the query never fires. The `getExistingSandbox()`
helper works around this by calling `listScenarios()` directly as a fallback
when the query cache is empty, making the auto-park flow work both in tests
and production (where the cache is warm from the page mount).

**Previous session**: 2026-04-29 (Phase 2.5c Slice 3.5 — post-smoke bug fixes)

**Previous session**: 2026-04-28 (Theming Slices 1 + 2 — full 12-theme catalogue + /settings)

Slice 2 (settings page + 11 more themes + accent picker) shipped on
top of Slice 1. The full 12-theme catalogue is now live, the
`/settings` route hosts theme + accent UI, and the sidebar gained a
Settings nav item.

- `themes.ts` — added 11 more theme objects (Tokyo Night Storm,
  Catppuccin Mocha + Latte, Nord, Dracula, One Dark, Rosé Pine,
  Gruvbox Dark + Light, Kanagawa, Solarized Light). Each fills all
  8 accent slots; where a source palette doesn't ship a slot
  (Dracula's blue, Rosé Pine's green, Solarized's teal) the closest
  authored hue is mapped in with a comment noting the choice.
- `themes.css` — 12 hand-authored `[data-theme='...']` blocks
  matching themes.ts exactly. The drift-check vitest grew from 25
  cases to 300 (24 assertions × 12 themes + parity).
- `app.html` — pre-hydrate THEMES map updated with all 12 ids and
  their dark/light modes so the right class lands on first paint
  before any JS hydrates.
- `frontend/src/routes/settings/+page.svelte` — new route. Sections:
  Theme grid (4×3 responsive cards with mini-swatch + name + ringed
  current marker), All/Dark/Light filter chips, 8 accent swatches
  using the *current theme's* native palette (clicking persists to
  localStorage and rewrites --primary/--ring/--chart-1 instantly),
  Preview card (primary button, outline button, accent link, body
  text sample, 7-bar chart sample using --chart-1).
- `+layout.svelte` — sidebar gains Settings nav item with the
  Settings icon, after Operations.
- `frontend/src/routes/settings/page.test.ts` — 5 vitest cases
  (renders all 12, mode chip filters to light, theme card click
  sets data-theme + writes localStorage, accent swatch click sets
  --primary + persists, accent slot carries across theme switch).

**Slices 1 + 2 status:** vitest 336/336 (was 31 pre-theming, +25
slice 1 drift-check, +275 slice 2 drift expansion = 300, +5 slice 2
page tests, +0 net for the rest). svelte-check 0/0. pytest 146/146
untouched.

Smoke (curl against docker stack): served HTML carries
`data-theme="tokyo-night"` on `<html>`; production CSS bundle at
`/_app/immutable/assets/0.RWfTfNqB.css` contains all 12
`[data-theme='...']` blocks; `/settings` route returns 200.

Earlier today (2026-04-28, Theming Slice 1 — Tokyo Night default +
theme infrastructure)

Brainstormed theming end-to-end via mockups + Q&A. Locked the design:
mix of dark + light themes (12 total), `/settings` page hosts the
selector, accent picker uses each theme's native 8-slot palette
(slot name carried across theme switches), CSS-var runtime swap with
localStorage persistence. Spec at
`docs/superpowers/specs/2026-04-28-theming-design.md`.

Shipped Slice 1 (infrastructure + Tokyo Night default):

- `frontend/src/lib/theme/{types.ts, themes.ts, theme-service.ts,
  themes.test.ts}` — Theme/ThemeTokens/AccentSlot types, Tokyo Night
  TS object, `setTheme()/setAccent()/initThemeOnHydrate()` Svelte
  store, drift-check vitest with 25 cases asserting themes.ts ↔
  themes.css parity.
- `frontend/src/themes.css` — `[data-theme='tokyo-night']` block.
- `frontend/src/app.html` — `<html data-theme="tokyo-night"
  class="dark">`; inline pre-hydrate `<script>` reads
  `localStorage.finclaide.theme` and applies the right `data-theme`
  + `dark`/`light` class before SvelteKit hydrates.
- `frontend/src/app.css` — dropped the inline `:root` token block
  (now lives per-theme in themes.css), tokenized body gradient via
  `--body-gradient`, imports `./themes.css`.
- `frontend/src/routes/+layout.svelte` — calls
  `initThemeOnHydrate()` on mount so accent slot from localStorage
  applies (only matters once Slice 2 ships the picker).
- Old custom palette retired. Tokyo Night is now the default.

**Slice 1 status:** vitest 56/56 (was 31, +25 from drift-check);
`npm run check` 0/0; backend untouched (pytest stays 146/146).
Smoke via curl + production-bundle inspection: served HTML has
`data-theme="tokyo-night"` on `<html>`, bundle CSS at
`/_app/immutable/assets/0.*.css` contains the full Tokyo Night
block with all expected tokens (#1a1b26 bg, #c0caf5 fg,
--body-gradient wired). Browser visual smoke deferred — chrome-
devtools MCP disconnected mid-session, will visual-verify on
slice 2 build.

Earlier session (2026-04-26, Phase 2.5c Slice 1 — Sandbox in place)

Brainstormed Phase 2.5c (what-if scenarios) end-to-end through the
visual-companion mockups + Q&A. Locked the four-state cycle (Active /
Sandbox / Saved / Projection) with explicit transitions, and shipped
Slice 1 — Sandbox in place — in this session.

- **Schema** — added nullable `plans.label` column (the existing
  `plans.name` is `NOT NULL` and holds the sheet/budget title, so a
  separate column carries the user-facing scenario name). Two partial
  unique indexes enforce invariants: `idx_plans_one_sandbox` on
  `(status)` where `status='scenario' AND label IS NULL` (at most one
  Sandbox), and `idx_plans_saved_label_unique` on `(label)` where
  `status='scenario' AND label IS NOT NULL` (no duplicate Saved
  names). New `_migrate_plans_add_label_column` migration runs
  between `_migrate_plans_status_widen` and `executescript(SCHEMA_SQL)`,
  idempotent on fresh and already-migrated installs.
- **PlanService** — new `create_scenario(from_plan_id, label=None)`
  deep-copies plan + categories with fresh ids; passes label
  through. `commit_scenario(scenario_id)` archives the prior-active
  for the same year, snapshots both the prior-active and the new-
  active states into `plan_revisions` with `source='migration'`, and
  flips the scenario row to `status='active'` clearing the label.
  `discard_scenario(scenario_id)` is a hard delete (CASCADE handles
  categories + revisions). `list_scenarios()` returns scenario rows
  newest-first with category counts.
- **API** — five new `/ui-api/scenarios/...` routes: list, detail,
  create (POST with `from_plan_id` + optional `label`), commit
  (`operation_lock.guard("plan_commit")`), delete. Editing scenario
  categories reuses the existing `PATCH /ui-api/plan/categories/{id}`
  handler — scenarios are just plans with `status='scenario'`.
- **Frontend** — `/planning` gains a "Try a what-if" / "Continue
  sandbox" button next to History. Clicking creates (or resumes) a
  sandbox; the page enters Sandbox mode in place via a viewedScenarioId
  state + dynamic scenario plan query (writable opts pattern from the
  History sheet). Sandbox banner with Discard / Commit confirmation
  modals. Mutations invalidate `['plan']`, `['scenarios']`, and
  `['summary']`.
- **Tests** — 21 new pytest cases in `tests/test_scenarios.py` cover
  schema migration (idempotent against a 2.5b-shape legacy fixture),
  create lifecycle (sandbox vs saved, uniqueness rejections), list,
  commit (archives prior active, records both attribution and
  post-commit revisions, allows new sandbox after commit), and
  discard. Full backend suite: 146/146.

**Slice 1 commits this session:**
- (this commit) Schema migration + PlanService scenario methods +
  `/ui-api/scenarios/...` routes + `/planning` Sandbox mode UI +
  21 pytest cases.
- Spec at `docs/superpowers/specs/2026-04-26-phase-2.5c-scenarios-design.md`
  (mirrors the brainstormed plan; covers slices 2–4 framework but no
  implementation past slice 1).

**Slice 1 status:** all unit tests pass; `npm run check` 0/0; `npx
vitest run` 31/31 (no new vitest cases this slice — sandbox toggle
test deferred to slice 2 alongside the Saved-scenarios surface).
Manual smoke through chrome-devtools against `docker compose up`
green end-to-end:
- Created sandbox from active (plan 4 from plan 3); banner appeared
  with Discard / Commit, page entered Sandbox mode in place, "Try a
  what-if" hidden.
- Edited Bills › 22nd - Claude $200 → $250 in sandbox; toast
  "Category saved"; sandbox total bumped $10,688.13 → $10,738.13;
  active plan unchanged.
- Committed sandbox; confirmation modal asked first; on confirm the
  banner disappeared, active plan now shows Claude $250, total
  $10,738.13, source flipped to "edited".
- DB inspection confirmed both attribution revisions: prior-active
  (plan 3, now archived) got `migration` / "Replaced by sandbox";
  new-active (plan 4) got `migration` / "Committed sandbox to active"
  plus the pre-commit `ui_update` for the $200 → $250 edit.
- History sheet on the new active shows both revisions newest-first.
- Zero console errors, zero warnings throughout.

Earlier session (2026-04-25, Phase 2.5b shipped end-to-end):

Built all three slices of Phase 2.5b on top of the spec at
`.docs/ai/phases/2.5b-versioning-rollback.md`:

- **Slice 1** (commit `4ea952c`) — `plan_revisions` table + index,
  widened `plans.status` CHECK to admit `'draft'/'scenario'` (with shadow-
  table migration for existing installs, run before SCHEMA_SQL so the
  view recreates against the migrated table), PlanService instrumentation
  on every write path (post-change snapshot stored as JSON, summary
  composed from the diff), `restore_revision` / `list_revisions` /
  `get_revision`, retention prune (last 50 OR last 7 days). 14 new
  pytest cases.
- **Slice 2** (commit `39cccd1`) — three endpoints on `/api/*` and
  `/ui-api/*` (list, detail, restore). Restore wraps
  `operation_lock.guard("plan_restore")` so it 409s during import/sync.
  Importer hook: `BudgetImporter._mirror_into_plan_model` now snapshots
  the about-to-be-archived plan as `source='importer'` tagged with the
  new plan_id, closing the lost-edit window. 9 new pytest cases.
  Restore re-inserts categories with fresh ids (the snapshot's original
  ids may already exist on archived plans whose `plan_categories` rows
  linger after archive).
- **Slice 3** (this commit) — `$lib/api.ts` gains revision schemas +
  `listPlanRevisions` / `getPlanRevision` / `restorePlanRevision`. New
  `frontend/src/components/plan-history-sheet.svelte` renders a right-
  side sheet with revision list, source badges, diff preview (snapshot
  vs current), and a confirm-then-restore flow that invalidates `['plan']`
  + `['summary']`. `/planning` grows a **History** button next to **Add
  row**, disabled while a budget import is busy. 3 new vitest cases at
  `frontend/src/routes/planning/history.test.ts`.

Earlier session (2026-04-24, post-merge test work):

- **Phase 0** — fast-forwarded `svelte-migration` (`b39b0ed`) into
  `main`. Commit `699ad52` updates handoff docs.
- **Phase 1** — `frontend/src/hooks.server.test.ts` regression guard
  with 8 cases (ingress + forwarded headers, precedence, normalizeBasePath
  edges, explicit `</head>` vs `%sveltekit.head%` guard). Commit `406d68b`.
- **Phase 2** — Svelte test scaffolding: `$app/*` mocks,
  `QueryClientProvider` harness, fixtures ported from
  `git show 69cc2e48~1:frontend/src/test/fixtures.ts`. Commit `c267a9a`.
- **Phase 3** — 18 React page-level vitest cases ported to Svelte:
  categories (1) `d325f7f`, operations (1, plus global `svelte-sonner`
  mock) `56f8454`, overview (1) `aa6be2a`, transactions (3 — required
  vitest 2 → 3.2.4 upgrade to align Vite versions; commits `9de0cc8` +
  `581c96b`), planning (7) `4d68044`, a11y (5, via layout-harness)
  `7992b0d`. Full suite 28/28; svelte-check 0/0.
- **Phase 4** — wrote the Phase 2.5b (Versioning & rollback) spec at
  `.docs/ai/phases/2.5b-versioning-rollback.md`. Design-only;
  implementation follows as a separate phase.

Previous session (2026-04-23):

Ran the full manual smoke of `svelte-migration` through Playwright MCP +
`curl`. Four routes (`/categories`, `/transactions`, `/planning`,
`/operations`) and the run-detail view (`/operations/runs/148`) all render
with zero console errors. Plan-edit round-trip verified: bumping
`Bills › 22nd - Claude` from $200 to $201 moved the summary payload's
`groups[Bills].planned_milliunits` from 7,116,040 → 7,117,040; revert
restored baseline. GroupChart SVG (aria-label "Plan vs actual by group")
re-renders from the updated summary.

Fixed a real regression in `frontend/src/hooks.server.ts`: the ingress
base-href injection never actually fired. `transformPageChunk` was calling
`html.replace('%sveltekit.head%', …)`, but SvelteKit substitutes that
placeholder in the template before streaming, so the replace was a no-op.
Switched the marker to `</head>`. Verified with curl:
- `X-Ingress-Path: /finclaide` → emits `<base href="/finclaide/">` plus the
  `window.__FINCLAIDE_BASE_PATH__` / `__FINCLAIDE_BASE_HREF__` globals.
- No header → falls back to `<base href="/">` (basePath normalises to ``).

The prior session's pytest case only verified that the header was
forwarded through the Flask proxy — it never asserted the rewrite. Now
that the rewrite actually happens, a Node-side vitest case for
`hooks.server.ts` is queued in next-steps.

Prior migration fixes still in place:

- Flask reverse proxy forwarded browser `Accept-Encoding: ... zstd` to
  SvelteKit and stripped `Content-Encoding`, so Chrome received compressed
  asset bytes as JavaScript and failed with `SyntaxError: Invalid or
  unexpected token`. `frontend.py` now forces upstream
  `Accept-Encoding: identity`; regression assertion added.
- `+layout.svelte` created the shell status query before the
  `QueryClientProvider` context existed. The layout now passes its explicit
  `queryClient` to `createQuery`.

Prior migration commit log on `svelte-migration`:

- `69cc2e4` — Slice 1: SvelteKit project skeleton (svelte.config.js,
  vite.config.ts, app.html, app.css verbatim Tailwind tokens, placeholder
  route). Removed all React files. vite ^6 (downgraded from ^7 for
  SvelteKit compat) + vitest ^2.
- `1c093ac` — Slice 2: lib utils + UI primitives. Ported `lib/api.ts`
  (verbatim Zod schemas), `format.ts`, `runtime.ts`, `utils.ts`. New
  `lib/stores/month.svelte.ts` (Svelte 5 rune store). 23 UI primitives
  wrapping bits-ui (Dialog, Sheet, Select, Tabs) plus pure-Tailwind
  Card/Button/Badge/Input/Skeleton/Table parts. Vitest setup with
  pointer-capture stubs + `resolve.conditions: ['browser']`. button
  smoke test passes (2/2).
- `f722987` — Slice 3: 9 domain components (status-chip, freshness-chip,
  metric-card, data-table, failure-cause-card, reconcile-preview-card,
  automation-status-card, plan-category-sheet, group-chart). DataTable
  is a hand-rolled wrapper (no @tanstack/svelte-table). GroupChart is a
  hand-rolled SVG bar chart (no recharts). svelte-sonner toasts.
- `9ff1213` — Slice 4: routes + hooks. All 6 React pages ported to
  SvelteKit file-based routing. AppShell in `+layout.svelte` with nav,
  freshness chips, scheduled-refresh banner, QueryClientProvider.
  `hooks.server.ts` injects HA ingress base path via `transformPageChunk`.
  Reactive query options use the writable-store + $effect pattern since
  this version of `@tanstack/svelte-query` only accepts `StoreOrVal`.
  Page-level vitest cases deferred to a follow-up if needed.
- `e46a8e9` — Slice 5: Flask reverse proxy. `frontend.py` rewritten to
  forward non-API paths to `FINCLAIDE_FRONTEND_URL` via httpx. `config.py`
  gains `frontend_url`. Two new pytest cases for proxy behavior.
- `7f45601` — Slice 6: Docker + addon. New `Dockerfile.web` (SvelteKit
  Node container). Trimmed root `Dockerfile` (Python only). Compose adds
  `web` service. HA add-on bundles both runtimes; `run.sh` starts
  `node build` alongside gunicorn before nginx.

## Build Status

- Backend: `pytest` — 190/193 pass (3 pre-existing infra failures:
  `test_api.py::test_healthcheck_and_dashboard_fallback`,
  `test_config.py::test_app_config_reads_home_assistant_options_file`,
  `test_mcp_server.py::test_finclaide_mcp_stdio_launch`; these require
  the Docker container's `/app/.venv` and are not regressions).
- Frontend: `npm run check` — `svelte-check` 0/0; `npx vitest run` —
  371/371 (was 369 pre-Phase-2.5d; +2 new ops-page tests for Publish button).

## Active Milestone

**Phase 2.5 (Native Planning Surface) is fully shipped** as of 2026-04-30.

**Phase 2.5e** (app-as-source-of-truth correction) shipped 2026-05-03 —
removes scheduled / refresh-all dependency on the workbook. See last-
session summary.

**Phase 3 (Decision Engine V1) is fully shipped** as of 2026-04-30:
- Slice 1 — Mid-month pace + year-end forecast on Home ✓
- Slice 2 — Anomaly explanations + narratives ✓ (510421b)
- Slice 3a — `/insights` route + per-category trend page ✓ (41a53b8)
- Slice 3b — Variance heatmap ✓ (7f430b8)
- Slice 4 — Recommendation grounding ✓ (this commit)

Both Phase 3 exit criteria met:
- "Weekly review reliably identifies spending shifts, overages, and outliers" ✓
- "The app explains *why* something is risky, not just that it is risky" ✓

Weekly review archive (mentioned in the spec for Slice 3) was descoped —
needs snapshot-storage schema; not justified now. Can land later if the
operator wants to track review history.

## Blockers

- None.
