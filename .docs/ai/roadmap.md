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

**Phase 1 — Trusted Core Data Flow (COMPLETE 2026-04-18)**

All sub-tasks shipped across three commits (`bbe6243`, `c0934c6`, `4676d2e`).
See `.docs/ai/phases/phase-1.md` for the full spec + report.

- [x] Surface failure causes in the dashboard. New `FailureCauseCard`
      component renders on Operations (with Retry buttons) and Overview
      (read-only) whenever any source's latest run failed.
- [x] `/api/reconcile/preview` (and `/ui-api` mirror): deterministic diff of
      planned vs YNAB names — missing-in-YNAB, extra-in-YNAB, exact-match
      counts. No mutations, no fuzzy matching.
- [x] Reconcile-preview auto-fetches and renders on Operations whenever the
      latest reconcile failed, with a one-click re-run button.
- [x] Plan staleness UX: header `FreshnessChip` for Plan + YNAB on every page,
      plus an `aria-live=polite` banner when scheduled refresh's last status
      is `failed` or `skipped`.
- [x] Run-detail view: `/api/runs/{id}` + `/operations/runs/:id` page that
      renders `details_json` as status-aware structured cards (success
      summary, failure block, skipped explanation) plus the raw payload.
- [x] Frontend baseline tests: 3 new transactions-page cases (pagination,
      filter, detail open) and 5 new header/nav a11y smoke cases.

**Exit criteria — met:**
- A failing import / sync / reconcile is diagnosable from the UI alone via
  FailureCauseCard + run-detail view (no JSON spelunking required).
- A missed scheduled refresh is impossible to overlook — top-level banner
  with the cause + link to Operations.
- Reconcile failures route through the new preview view automatically.

**Test status**: pytest 70/70, vitest 12/12, TypeScript clean.

## Next Active Milestone

**Phase 2.5b — Versioning & rollback** is now next. Plan + spec required:
`plan_revisions` schema, retention policy, rebuild of `plans` table to
extend the `status` CHECK constraint with 'draft' / 'scenario'. After
2.5b, scenarios (2.5c) and publish-to-Sheets (2.5d) follow.

## Upcoming Milestones (named, not yet active)

**Phase 2 — Continuous Planning Ingestion** (COMPLETE 2026-04-18)

- [x] Failure-mode coverage of `ScheduledRefreshService` — skip-when-locked
      and reconcile-failure-recorded were already covered by
      `test_scheduled_refresh_skip_is_reflected_in_status` and
      `test_scheduled_refresh_failure_is_reflected_in_status`. Added
      `test_scheduler_skips_bootstrap_when_prior_runs_succeeded` to close
      the missing inverse case.
- [x] `AutomationStatusCard` hoists scheduled-refresh status to a dedicated
      Operations card showing `next_run_at` (with relative countdown), last
      finished, last status, and last error. Removed the redundant copy
      from the Status sidebar.

**Phase 2.5 — Native Planning Surface** (split into a/b/c/d)

Goal: app becomes canonical for the plan; spreadsheet is an exported artifact.

- **2.5a — Plan model + editor + migration (COMPLETE 2026-04-19)**
  - [x] SQLite `plans` + `plan_categories` tables + partial unique index
        ("one active plan per year"). `v_latest_planned_categories` rebuilt
        as a compatibility shim so existing consumers (reconcile / summary /
        analytics) see no change.
  - [x] `PlanService` (CRUD + rename) at `src/finclaide/plan_service.py`.
  - [x] Importer mirrors into the new model atomically; archives the prior
        active plan for the year.
  - [x] One-shot startup hydration from latest `budget_imports` for upgrades.
  - [x] React `/planning` page with 5 block tabs and click-to-edit Sheet.
        Delete with confirm. Rename behind a checkbox (intentional friction).
  - Commits: `761d387`, `121089e`, `0159407`. See
    `.docs/ai/phases/phase-2-5a.md`.

- **2.5b — Versioning & rollback (next)**
  - [ ] `plan_revisions` snapshots every save (diff + restore via UI).
  - [ ] Extend `plans.status` CHECK to allow 'draft' / 'scenario' (requires
        SQLite table rebuild).
  - [ ] Closes the lost-edit window if the importer overwrites in-flight
        edits.

- **2.5c — What-if scenarios**
  - [ ] Branch off active plan; edit; compare projected variance vs actuals;
        commit or discard.

- **2.5d — Publish-to-Sheets**
  - [ ] Round-trip into the configured Google Sheet using the importer-
        compatible 4-block layout. `.xlsx` download path for offline sharing.

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
