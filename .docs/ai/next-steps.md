# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [ ] Phase 2 sweep: add failure-mode tests for `ScheduledRefreshService`
      (operation-lock skip path, reconcile-failure recording, bootstrap
      respects prior success). One file in `tests/`, no production changes.
- [ ] Phase 2 sweep: pull `scheduled_refresh.next_run_at` and `last_status`
      into a more prominent panel on Operations (currently buried in the
      Status sidebar). Small frontend-only change.

## Soon

- [ ] Brainstorm + author Phase 2.5 spec (Native Planning Surface) under
      `.docs/ai/phases/phase-2-5-spec.md`. Cover: SQLite plan model,
      editor UX shape, what-if scenario branching, versioning/rollback,
      publish-to-Sheets export protocol.
- [ ] Dispatch a Haiku batch (4 items in parallel) once Phase 2 sweep
      lands — magic-number comments, unused imports, icon-button titles,
      empty-state messaging.

## Deferred

- Phase 3 work (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds) — not until Phase 2 + Phase 2.5 land.
- Sonnet backlog items that depend on Phase 2.5's plan model (e.g.
  variance drill-down) should wait.
- Phase 7 (iOS / household visibility) — no movement planned.
