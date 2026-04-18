# Roadmap

> Canonical phase definitions live in `docs/roadmap.md`. This file holds the
> active milestone breakdown, the tiered backlog for parallel AI work, and
> Claude-specific operating rules.

## Vision

Finclaide — private household finance OS. Dashboard-first, YNAB for actuals,
in-app planning replacing the spreadsheet over time, AI as advisor. Single
household, single plan, not a public SaaS.

## Source-of-Truth Direction (2026-04)

- **Actuals**: YNAB. Unchanged.
- **Plan (today)**: `2026 Budget` sheet in `Budget.xlsx` (local / remote URL /
  Google Sheets via service account). Imported via `BudgetImporter`.
- **Plan (target)**: SQLite, edited in the React UI. The spreadsheet becomes
  an exported artifact for sharing/backup. Importer stays as a migration path.
  This shift is delivered in Phase 2.5.

## Active Milestone

**Phase 1 — Trusted Core Data Flow (rescoped)**

Original goal stands: import, sync, and reconcile must be dependable every
week. The pieces still missing in real weekly use:

- [ ] Surface failure causes in the dashboard. Operations page shows raw run
      JSON; users should see the cause of the last failure as a first-class
      card with the actionable next step.
- [ ] `/api/reconcile/preview` (and `/ui-api` mirror): deterministic diff of
      planned vs YNAB names — missing-in-YNAB, extra-in-YNAB, exact-match
      counts. No mutations, no fuzzy matching yet.
- [ ] Reconcile-preview surfaces on Overview banner and Operations panel
      whenever the latest reconcile failed; one-click re-run after fixes.
- [ ] Plan staleness UX: header freshness chip driven by
      `status.plan_freshness` / `status.sync_freshness`, plus a banner when
      scheduled refresh has skipped or failed its last cycle.
- [ ] Run-detail view: `/api/runs/{id}` + `/operations/runs/:id` page that
      renders `details_json` (incl. `error`) as a structured card rather than
      a JSON dump.
- [ ] Frontend baseline tests for the transactions page and a11y smoke for the
      header/nav (currently uncovered).

**Exit criteria** — A failing import / sync / reconcile is diagnosable from
the UI alone, and a missed scheduled refresh is impossible to overlook.

## Upcoming Milestones (named, not yet active)

**Phase 2 — Continuous Planning Ingestion** (sweep, mostly shipped)

- [ ] Failure-mode coverage of `ScheduledRefreshService` (skip when locked,
      reconcile failures recorded as `status="failed"`, bootstrap respects
      prior success — tests for each).
- [ ] Surface scheduled refresh `last_status` and `next_run_at` more
      prominently on Operations.

**Phase 2.5 — Native Planning Surface (NEW, post-Phase-1)**

Goal: app becomes canonical for the plan; spreadsheet is an exported artifact.

- [ ] Plan model in SQLite (`plans` + `plan_categories` tables) and a
      `PlanService` that abstracts read/write. Importer writes into the new
      shape rather than the legacy `planned_*` tables — or both, briefly.
- [ ] Editor surfaces in the React UI:
  - monthly category rows (group/name/planned/notes)
  - annual + one-time blocks (with due month)
  - stipends and savings as first-class blocks
- [ ] What-if scenarios: branch off the active plan, edit, compare projected
      variance vs actuals, then commit or discard.
- [ ] Versioning & rollback: every save snapshots; diff and restore via UI.
- [ ] Publish-to-Sheets export: writes the current plan back into the
      configured Google Sheet (preserves the existing layout) and offers an
      `.xlsx` download path for offline sharing.
- [ ] Migration: read the latest workbook import, hydrate the new model, mark
      it as the active plan.

**Phase 3 — Decision Engine V1**

- [ ] Standalone pages for `analytics/trends`, `projection`, `anomalies`,
      `recommendations`, `aggregate` — currently consumed only by the weekly
      review composer.
- [ ] Reconcile **suggested mappings** (follow-up to Phase 1 preview) —
      ranked rename candidates with explicit confirm; no silent aliasing.
- [ ] Configurable thresholds: replace scattered magic numbers
      (`analytics.py:185, 467, 609, 666, 682-683`; `services.py:656, 668,
      830, 866, 872, 1051`) with a single configurable `THRESHOLDS` source.
- [ ] Variance drill-down: click an over-budget category in summary →
      transactions filtered to that category for that month.

**Phase 4-8** — see `docs/roadmap.md`. Cash flow & forecasting, goals &
savings (partly obviated by 2.5), operational review workflows, household /
iOS companion, AI copilot.

## Backlog (parallel, tiered by model capability)

<!-- tier3_owner: claude -->

Items are independent and low-risk; safe for a fresh agent with no session
context. Always cite file:line. Claim by changing `[ ]` → `[~]` and
committing. Skip `[~]` items — another agent owns them.

### Haiku (mechanical, no judgment)

- [ ] Extract Recharts inline style objects to constants —
      `frontend/src/components/group-chart.tsx:49-66`.
- [ ] Memoize `GroupChart` with `React.memo` —
      `frontend/src/components/group-chart.tsx:16`.
- [ ] Remove unused `Dialog` and `Tabs` shadcn imports from `App.tsx` and
      delete corresponding files in `frontend/src/components/ui/` if no
      consumers remain — `frontend/src/App.tsx`.
- [ ] Add `title` attributes to icon-only `RefreshCw` operation buttons —
      `frontend/src/pages/operations-page.tsx`.
- [ ] Add `aria-label` (or text-shadow variant) to `StatusChip` so status is
      not color-only — `frontend/src/components/status-chip.tsx:24`.
- [ ] Add explicit empty-state copy to the transactions page (today it falls
      back to the generic `DataTable` empty message) —
      `frontend/src/pages/transactions-page.tsx`.
- [ ] Replace bare `except Exception` in `financial_health_check` projection
      guard with `except (DataIntegrityError, ValueError)` and log the swallow
      — `src/finclaide/analytics.py:684`.
- [ ] Use sample variance (`n - 1`) in `_stddev` for >2 samples; document the
      choice — `src/finclaide/analytics.py:47-52`.
- [ ] Hoist `PAGE_SIZE = 25` and other hardcoded pagination/heights to a
      single layout constants module —
      `frontend/src/pages/transactions-page.tsx:30`,
      `frontend/src/components/group-chart.tsx:24`.
- [ ] One-line comments explaining each magic threshold in `_overage_watch`
      and `weekly()` — `src/finclaide/services.py:656, 668, 830, 866, 872,
      1051` (no behavior change).

### Sonnet (some architectural judgment)

- [ ] Add a `THRESHOLDS` dataclass in `src/finclaide/thresholds.py` and route
      all overage / freshness / sigma / variance numbers through it. Keep
      defaults identical; allow env overrides. Touches `services.py` and
      `analytics.py`.
- [ ] Split `ReportService.summary()` (`services.py:300-438`) into focused
      helpers: `_load_planned`, `_load_actuals`, `_compute_overage_watch`,
      `_compose_summary`. No behavior change; tests must remain green.
- [ ] Split `_overage_watch()` (`services.py:562-701`) into
      `_analyze_spend_series`, `_compute_shortfall`, `_categorize_watch_level`.
- [ ] Split `AnalyticsService.detect_anomalies()` (`analytics.py:316-441`)
      into `_detect_transaction_anomalies` and `_detect_category_anomalies`.
- [ ] Split `financial_health_check()` (`analytics.py:593-711`) into
      `_check_sync_freshness`, `_check_reconciliation`, `_check_budget_import`,
      `_check_projection`. Each returns a list of alerts.
- [ ] Add a transactions-page test in
      `frontend/src/test/transactions-page.test.tsx` covering: pagination
      next/prev, filter by group, detail-sheet open/close.
- [ ] Add a top-level React error boundary around the lazy route Suspense in
      `frontend/src/App.tsx` with a fallback that links to Operations and
      logs to console.
- [ ] Surface failure causes on Operations: parse `details_json.error` for
      the latest failed run of each source and render as a Card —
      `frontend/src/pages/operations-page.tsx`. Backend already provides the
      data via `/ui-api/status` and `/ui-api/runs`.
- [ ] Add `/api/runs/{id}` (and `/ui-api` mirror) returning the full
      `sync_runs` row including `details_json` —
      `src/finclaide/api.py`, `src/finclaide/ui_api.py`,
      `src/finclaide/services.py`.

### Opus (design skill, cross-cutting — owned by Claude)

Reserved for the active and upcoming milestones above. Do not start Opus-tier
work without an explicit phase spec and the user's go-ahead.

## Priority Order

1. Phase 1 sub-tasks (active milestone) — Opus-tier, executed against a phase
   spec.
2. Sonnet backlog that unblocks Phase 1 (failure-cause card, runs detail
   endpoint).
3. Haiku backlog — runs alongside any phase, in parallel batches.
4. Phase 2 sweep, then Phase 2.5 spec.

## Constraints

- Do not weaken strict data integrity or exact-match reconciliation. Phase 1's
  preview/diagnostics endpoint must NOT mutate data or auto-rename categories.
- Keep `/api/*` machine-friendly and stable. Additions must not break existing
  shapes; bump payload fields additively.
- Money is integer milliunits everywhere on the wire and in storage.
- Prefer behavior-level tests over manual validation. Importer / reconcile /
  money-handling changes require deterministic tests in the same change.
- Private tool. Do not introduce multi-tenant auth, billing, or self-serve
  onboarding without an explicit roadmap shift.
