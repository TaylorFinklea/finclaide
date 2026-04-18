# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [ ] Brainstorm Phase 2.5 (Native Planning Surface) with the user. Key
      open questions:
  - SQLite plan model shape: keep the existing `planned_groups` /
    `planned_categories` tables and add a `plans` parent + version
    snapshots, or migrate to a fresh schema?
  - Editor UX shape: per-block tabs vs unified table?
  - What-if branching: how do scenarios reference / diff the active
    plan? Soft-fork at the row level, or full snapshot copy?
  - Publish-to-Sheets: write into the configured Google Sheet using the
    same layout the importer expects (round-trip safe), or a separate
    "export" sheet?
- [ ] Author Phase 2.5 spec under `.docs/ai/phases/phase-2-5.md` once
      brainstorm answers the above.

## Soon

- [ ] Dispatch a Haiku batch (4 items in parallel) once Phase 2.5 spec is
      signed off — magic-number comments, unused imports, icon-button
      titles, empty-state messaging.

## Deferred

- Phase 3 work (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds) — not until Phase 2.5 lands.
- Sonnet backlog items that depend on the new plan model (variance
  drill-down, threshold extraction) should wait for Phase 2.5.
- Phase 7 (iOS / household visibility) — no movement planned.
