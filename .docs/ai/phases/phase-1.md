# Phase 1 — Trusted Core Data Flow

**Status**: Complete (2026-04-18)
**Owner**: Claude (tier3_owner)
**Commits**: `bbe6243`, `c0934c6`, `4676d2e`

## Goal

Make import, sync, and reconcile diagnosable from the dashboard alone. The
plumbing existed; the visibility did not.

## Sub-tasks (all shipped)

1. **Failure-cause surfacing** — `FailureCauseCard` component lists every
   source whose latest run failed, with the captured error, a deep link into
   the new run-detail page, and (on Operations) a Retry button. Renders
   nothing when no failures exist. Used on both Overview (read-only) and
   Operations (with retry).

2. **Reconcile preview endpoint + UX** — new `/api/reconcile/preview` (and
   `/ui-api` mirror) returns three classifications of every planned category
   against the current YNAB state:
   - `exact_matches` — planned name found in YNAB
   - `missing_in_ynab` — planned but absent (this is the cause of reconcile
     failures)
   - `extra_in_ynab` — present in YNAB but not in the plan (often a renamed
     category or a YNAB-side addition)

   Filters out hidden + deleted YNAB groups and categories. **No mutations,
   no fuzzy matching.** A `ReconcilePreviewCard` automatically fetches the
   preview on Operations whenever the latest reconcile failed, with a
   one-click re-run button after the user fixes things.

3. **Plan-staleness UX** —
   - Header now shows `FreshnessChip` for Plan + YNAB on every page (status
     + hours-stale).
   - App shell renders a banner above the route content when scheduled
     refresh's last status is `failed` or `skipped`. Banner uses
     `role=status` + `aria-live=polite` so screen readers announce it.

4. **Run-detail view** — new `/api/runs/{id}` (and `/ui-api` mirror) returns
   the full `sync_runs` row with parsed `details_json`. New lazy route
   `/operations/runs/:id` renders a structured outcome block (success /
   failure / skipped) plus the raw details payload. Recent Runs entries on
   Operations are now clickable links into this page.

5. **Test gap closure** — 3 new transactions-page cases (pagination,
   filter, detail-sheet open/close) and 5 new header/nav a11y smoke cases.

## Notable design decisions made during execution

- **Reconcile preview filters by `hidden=0` AND `deleted=0` on both groups
  and categories.** This excludes the YNAB internal master category group
  ("Inflow: Ready to Assign", etc.) without hard-coding a name list. May
  need refinement later if Credit Card Payments categories show up as
  noise; deferred until reported.
- **`status.latest_runs` now includes the run `id` field.** Lets the
  failure card deep-link to the run-detail page without a second fetch.
- **Failure card on Overview is intentionally read-only** (no Retry
  buttons). Users navigate to Operations to retry. Reduces the duplication
  of mutation logic and keeps Overview a "what's going on" surface rather
  than a control panel.
- **jsdom pointer-capture stubs** added to `frontend/src/test/setup.ts`
  (`hasPointerCapture`, `setPointerCapture`, `releasePointerCapture`,
  `scrollIntoView`). Enables Radix Select component tests now and in the
  future.

## Exit criteria

- [x] A failing import / sync / reconcile is diagnosable from the UI alone.
- [x] A missed scheduled refresh is impossible to overlook.
- [x] Reconcile failures route through the new preview view so the user
      knows which categories drifted before re-running.

## Verification

- Backend: `pytest` — 70/70 pass (7 new tests for the new endpoints).
- Frontend: `vitest run` — 12/12 pass (3 new transactions-page cases, 5 new
  a11y cases, plus the pre-existing 4 that needed minor updates to
  acknowledge the new failure-cause surfacing).
- TypeScript: `tsc --noEmit -p tsconfig.app.json` — clean.

## Out-of-scope for this phase (deferred)

- Suggested-mapping reconcile (ranked rename candidates) — Phase 3.
- Reconcile preview also rendering inline on Overview — current Overview
  surfaces the failure via `FailureCauseCard`, which links to Operations
  for the full preview. Sufficient for v1.
- Configurable thresholds (freshness hours, sigma) — Sonnet backlog item.
- Refactor of long methods in `services.py` / `analytics.py` — Sonnet
  backlog items, no behavioral change.

## Files touched

**Backend:**
- `src/finclaide/services.py` — `ReportService.run_by_id`, `ReconciliationService.preview`, added `id` to `latest_runs`
- `src/finclaide/api.py` — two new routes
- `src/finclaide/ui_api.py` — two new mirror routes
- `tests/test_api.py` — 7 new tests

**Frontend (new):**
- `frontend/src/components/freshness-chip.tsx`
- `frontend/src/components/failure-cause-card.tsx`
- `frontend/src/components/reconcile-preview-card.tsx`
- `frontend/src/pages/run-detail-page.tsx`
- `frontend/src/pages/transactions-page.test.tsx`
- `frontend/src/test/a11y.test.tsx`

**Frontend (modified):**
- `frontend/src/App.tsx` — lazy route, header chips, scheduled-refresh banner
- `frontend/src/lib/api.ts` — new schemas + `getRun` + `getReconcilePreview`
- `frontend/src/pages/operations-page.tsx` — failure card, preview card, clickable runs
- `frontend/src/pages/overview-page.tsx` — failure card at top
- `frontend/src/pages/operations-page.test.tsx` — updated for new failure surfacing
- `frontend/src/test/setup.ts` — jsdom pointer-capture stubs
