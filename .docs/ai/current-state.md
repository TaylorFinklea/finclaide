# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main`

## Last Session Summary

**Date**: 2026-04-18

Reset the AI handoff suite based on a deep codebase walkthrough. Key changes:

- Switched `tier3_owner` from `codex` to `claude` in `.docs/ai/roadmap.md`.
- Rescoped Phase 1 from a broad "trusted data flow" goal to a concrete
  punch-list of the visibility gaps still felt in weekly use (failure-cause
  surfacing, reconcile preview, plan-staleness UX, run-detail view, FE test
  baseline).
- Inserted Phase 2.5 ("Native Planning Surface") into `docs/roadmap.md` —
  app becomes canonical for the plan; spreadsheet becomes an exported
  artifact. Plan v1 must cover row editing, annual/one-time/sinking-fund
  blocks, what-if scenarios, versioning/rollback, and publish-to-Sheets.
- Populated the Haiku and Sonnet backlogs in `.docs/ai/roadmap.md` with
  ~20 items, each with file:line references.
- Recorded the source-of-truth direction shift, tier3 transfer, and the new
  reconcile-preview policy in `.docs/ai/decisions.md`.

No code changes this session — docs only.

## Build Status

- Not re-run this session. Last known green per `make test`. CI not present
  in repo.
- Frontend tests: 4 files (App, Overview, Operations, Categories). No
  transactions-page coverage yet (tracked in Sonnet backlog).

## Active Milestone

Phase 1 — Trusted Core Data Flow (rescoped). See
`.docs/ai/roadmap.md#active-milestone`. Awaiting plan-mode approval to
write the Phase 1 spec under `.docs/ai/phases/`.

## Blockers

- None.
