# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main`

## Last Session Summary

**Date**: 2026-04-18

Shipped Phase 1 (Trusted Core Data Flow) and Phase 2 (Continuous Planning
Ingestion) end-to-end.

Phase 1 — three commits:
- `bbe6243` — backend: `/api/runs/{id}` + `/api/reconcile/preview`
- `c0934c6` — frontend: failure-cause card, freshness chips, reconcile
  preview card, run-detail page, scheduled-refresh banner
- `4676d2e` — tests: transactions page (3 cases), header/nav a11y (5)
- `9235962` — handoff doc updates

Phase 2 sweep — pending commit:
- Added `test_scheduler_skips_bootstrap_when_prior_runs_succeeded` to
  cover the only missing failure-mode case (other three were already
  shipped in `test_api.py`).
- New `AutomationStatusCard` component hoists scheduled-refresh status
  out of the Status sidebar and into a dedicated card on Operations,
  showing `next_run_at` with a relative countdown, last finished /
  started timestamps, last status, and last error.
- Removed the now-orphaned `describeScheduleStatus` /
  `describeScheduleHeadline` / `describeScheduleDetail` helpers from
  `operations-page.tsx`.

## Build Status

- Backend: `pytest` — 71/71 pass (1 new bootstrap test).
- Frontend: `vitest run` — 12/12 pass.
- Frontend: `tsc --noEmit -p tsconfig.app.json` — clean.

## Active Milestone

**Phase 2.5 — Native Planning Surface**. Brainstorm + spec next, no code
until aligned. See `.docs/ai/roadmap.md` for the sub-task list.

## Blockers

- None.
