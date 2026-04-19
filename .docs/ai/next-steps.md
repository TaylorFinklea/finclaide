# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [ ] Spend a session on the live editor — drive `/planning` end-to-end
      against real Docker, exercise edit / create / delete on each block,
      and confirm the Overview's plan-vs-actual chart picks up edits after
      a refresh. Validates the shim under real data, not just fixtures.
- [ ] Brainstorm Phase 2.5b (Versioning & rollback). Open questions:
      - Per-save snapshot vs explicit "save version" + named snapshots?
      - Retention policy (last N? per-day? unlimited until manual prune?).
      - How to extend `plans.status` CHECK constraint to add 'draft' /
        'scenario' — SQLite ALTER doesn't support modifying CHECK, so it
        requires a CREATE NEW + INSERT SELECT + DROP + RENAME.
      - Diff UI shape — side-by-side vs row-level inline?

## Soon

- [ ] Author Phase 2.5b spec under `.docs/ai/phases/phase-2-5b.md` once
      brainstorm answers the above.
- [ ] Dispatch a Haiku batch (4 items in parallel) once 2.5b spec is
      signed off — magic-number comments, unused imports, icon-button
      titles, empty-state messaging.

## Deferred

- Phase 2.5c (what-if scenarios) — depends on 2.5b's revision model.
- Phase 2.5d (publish-to-Sheets round-trip) — independent of 2.5b/c but
  not next on the list.
- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds) — after Phase 2.5 fully lands.
- Phase 7 (iOS / household visibility) — no movement planned.
