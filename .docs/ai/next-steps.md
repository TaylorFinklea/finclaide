# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [x] Manual smoke of the `svelte-migration` branch (2026-04-23).
- [x] Fix ingress base-href regression (`hooks.server.ts` matches
      `</head>` instead of the already-substituted `%sveltekit.head%`).
- [x] Merge `svelte-migration` → `main` (fast-forward, 2026-04-24).
- [~] Phase 1: vitest regression guard for `hooks.server.ts`. File
      `frontend/src/hooks.server.test.ts`, 5–7 cases including an
      explicit guard that the match target is `</head>` not
      `%sveltekit.head%`.

## Soon

- [ ] Phase 2: Svelte test scaffolding — extend `frontend/src/test/
      setup.ts` with `$app/*` mocks, add `frontend/src/test/render-
      page.ts` (`QueryClientProvider` wrapper), port fixtures from
      `git show main~10:frontend/src/test/fixtures.ts`.
- [ ] Phase 3: port 18 React page-level vitest cases to Svelte
      `+page.test.ts`. Order: categories (1) → operations (1) →
      overview (1) → transactions (3) → planning (7) → a11y (5). One
      commit per file.
- [ ] Phase 4: write Phase 2.5b spec at
      `.docs/ai/phases/2.5b-versioning-rollback.md` — `plan_revisions`
      schema, retention, `plans.status` CHECK rebuild, UI surface,
      race-window fix, test strategy. No code.

## Deferred

- Phase 2.5c (what-if scenarios), 2.5d (publish-to-Sheets) — after 2.5b.
- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds).
- Phase 7 (iOS / household visibility) — no movement planned.
- React-era Sonnet backlog items — re-frame against the new Svelte file
  paths now that the migration has merged.
