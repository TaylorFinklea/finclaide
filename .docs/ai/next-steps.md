# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [x] Manual smoke of the `svelte-migration` branch:
  - [x] `docker compose up --build -d`
  - [x] `curl http://127.0.0.1:8050/healthz` hits Flask (not proxied).
  - [x] Browse `/` — dashboard mounts after proxy/query-client fixes.
  - [x] Browse `/categories`, `/transactions`, `/planning`,
    `/operations`, `/operations/runs/148` — all render with the same
    layout as the React version, 0 console errors.
  - [x] Edit a planned category and confirm Overview's chart updates
    (verified via summary payload delta; baseline restored after).
  - [x] Send a request with `X-Ingress-Path: /finclaide` and confirm the
    `<base href="/finclaide/">` tag appears. Required a hook fix:
    `transformPageChunk` now matches `</head>` instead of the (already-
    substituted) `%sveltekit.head%` placeholder.
- [ ] Commit the hook fix (`frontend/src/hooks.server.ts`) and the
      handoff doc updates, then merge `svelte-migration` → `main`.

## Soon

- [ ] Add a vitest case for `hooks.server.ts` that asserts the injection
      under and without `X-Ingress-Path`. Keeps us from shipping a silent
      no-op replace again.
- [ ] Port the 19 React vitest page-level cases to Svelte
      (`+page.test.ts`) to restore the test floor before resuming Phase
      2.5b. Test infra is already in place (button.test.ts proves the
      pipeline works); needs proper mocking of `getStatus`/`getSummary`
      etc. plus a `QueryClientProvider` wrapper.
- [ ] Brainstorm + spec Phase 2.5b (Versioning & rollback) on the
      Svelte stack.

## Deferred

- Phase 2.5c (what-if scenarios), 2.5d (publish-to-Sheets) — after 2.5b.
- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds).
- Phase 7 (iOS / household visibility) — no movement planned.
- React-era Sonnet backlog items — re-frame against the new Svelte file
  paths after the migration merges.
