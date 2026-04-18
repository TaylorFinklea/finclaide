# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [ ] Plan Phase 1 (Trusted Core Data Flow, rescoped) per the
      phase-execution protocol in `docs/ai-workflows/phase-execution.md`.
      Author the spec under `.docs/ai/phases/phase-1-spec.md` once user
      enters plan mode.
- [ ] Review the Sonnet backlog and decide which items should run in the
      same change-set as Phase 1 (failure-cause card, `/api/runs/{id}` are
      tightly coupled to Phase 1 deliverables).

## Soon

- [ ] Dispatch a Haiku batch (4 items in parallel, different files) once
      Phase 1 spec is approved — magic-number comments, unused imports,
      icon-button titles, empty states.
- [ ] Phase 2 sweep: add failure-mode tests for `ScheduledRefreshService`.
- [ ] Author Phase 2.5 brainstorm + spec for in-app planning surface
      (target schema, editor UX, scenario branching, Sheets-export
      protocol).

## Deferred

- Phase 3+ work (analytics surfacing, suggested-mapping reconcile,
  configurable thresholds) — not until Phase 1 + Phase 2 sweep land.
- iOS / household visibility (Phase 7) — no movement planned.
