# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [x] Phase 2.5b Slice 1 — `plan_revisions` table + PlanService
      instrumentation + retention prune + tests (commit `4ea952c`).
- [x] Phase 2.5b Slice 2 — three revision API endpoints + importer
      snapshot hook + tests (commit `39cccd1`).
- [x] Phase 2.5b Slice 3 — History sheet UI + restore confirm + tests
      (this session).
- [ ] Optional: docker-compose + browser smoke of the History flow.
      Edit a category, open History, click the just-created revision,
      confirm Restore, verify the planning page reverts and a new
      `restore` revision lands at the top of the list.

## Soon

- [ ] Phase 2.5c — What-if scenarios. Foundation now in place
      (`plans.status` admits `'scenario'`; `plan_revisions` already
      tracks per-plan history). Spec needs: branch-from-active flow,
      compare-projection vs current actuals, commit/discard semantics.
- [ ] Phase 2.5d — Publish-to-Sheets export. Round-trip the active
      plan back into the configured Google Sheet using the importer-
      compatible 4-block layout. `.xlsx` download path for offline
      sharing.

## Deferred

- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds).
- Phase 7 (iOS / household visibility) — no movement planned.
- React-era Sonnet backlog items — re-frame against the Svelte file
  paths now that the migration has merged.
