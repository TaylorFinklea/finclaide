# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [x] Manual smoke of the `svelte-migration` branch (2026-04-23).
- [x] Fix ingress base-href regression (`hooks.server.ts` matches
      `</head>` instead of `%sveltekit.head%`).
- [x] Merge `svelte-migration` → `main` (fast-forward, 2026-04-24).
- [x] Phase 1: vitest regression guard for `hooks.server.ts`
      (8 cases, commit `406d68b`).
- [x] Phase 2: Svelte test scaffolding — `$app/*` mocks,
      QueryClientProvider harness, fixtures ported (commit `c267a9a`).
- [x] Phase 3: port 18 React page-level vitest cases — categories (1),
      operations (1), overview (1), transactions (3), planning (7),
      a11y (5). Full suite 28/28.
- [x] Phase 4: Phase 2.5b spec at
      `.docs/ai/phases/2.5b-versioning-rollback.md`.
- [ ] Review + approve the Phase 2.5b spec. If changes are needed,
      iterate; otherwise proceed to Slice 1.

## Soon

- [ ] Phase 2.5b Slice 1 — `plan_revisions` table, `plans.status`
      CHECK migration, PlanService write-path instrumentation, retention
      prune, backend tests. No API, no UI. Must land with a full pytest
      green signal.
- [ ] Phase 2.5b Slice 2 — three revision API endpoints + importer
      snapshot hook + API tests.
- [ ] Phase 2.5b Slice 3 — `/planning` History sheet + restore UI +
      frontend tests. Playwright smoke of edit → History → restore flow.

## Deferred

- Phase 2.5c (what-if scenarios), 2.5d (publish-to-Sheets) — after 2.5b
  ships end-to-end.
- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds).
- Phase 7 (iOS / household visibility) — no movement planned.
- React-era Sonnet backlog items — re-frame against the new Svelte
  file paths now that the migration has merged.
