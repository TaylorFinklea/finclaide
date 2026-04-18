# Phase 2 — Continuous Planning Ingestion

**Status**: Complete (2026-04-18)
**Owner**: Claude
**Scope**: Sweep only — most of Phase 2's substance shipped earlier (Google
Sheets import, scheduled refresh thread, run history, freshness scoring).

## Goal

Close the two remaining gaps from the original Phase 2 list:
1. Failure-mode test coverage for `ScheduledRefreshService`.
2. More prominent surfacing of `last_status` and `next_run_at` on Operations.

## Outcome

**Tests** — three of the four failure-mode cases were already covered in
`test_api.py` (skip-when-locked, reconcile-failure recording, bootstrap
fires on first run). Added the one missing inverse case:

- `test_scheduler_skips_bootstrap_when_prior_runs_succeeded` — seeds prior
  successful `budget_import` and `ynab_sync` runs in the shared
  `tmp_path` DB via a first app instance, spins up a second app with
  bootstrap enabled, stops the thread, and asserts
  `_should_bootstrap()` returns `False`.

**UI** — new `AutomationStatusCard` component placed between the
`ReconcilePreviewCard` and the Operations control grid. Shows:
- Next run timestamp + relative countdown (e.g. "In 23 min").
- Last finished + started timestamps.
- Last status with the StatusChip color, plus last error if any.
- Border tone (rose / amber / emerald / neutral) tied to last status.
- A separate "disabled" variant when scheduled refresh is off.

Removed the redundant Scheduled Refresh subsection from the Status
sidebar to avoid duplication. Three orphaned helper functions
(`describeScheduleStatus`, `describeScheduleHeadline`,
`describeScheduleDetail`) deleted from `operations-page.tsx`.

## Verification

- Backend: `pytest` — 71/71 pass.
- Frontend: `vitest run` — 12/12 pass (existing tests unaffected).
- Frontend: `tsc --noEmit -p tsconfig.app.json` — clean.

## Files touched

**Backend:**
- `tests/test_api.py` — 1 new test.

**Frontend (new):**
- `frontend/src/components/automation-status-card.tsx`

**Frontend (modified):**
- `frontend/src/pages/operations-page.tsx` — import + render
  AutomationStatusCard; remove Scheduled Refresh from Status sidebar;
  delete three orphaned helper functions.

## Out of scope (deferred)

- Any production change to `ScheduledRefreshService` itself — the existing
  behavior is correct; we only needed the test gap closed.
- Configurable refresh interval per environment — Sonnet backlog.
