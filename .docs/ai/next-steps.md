# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [ ] Manual smoke of the `svelte-migration` branch:
  - [x] `docker compose up --build -d`
  - [x] `curl http://127.0.0.1:8050/healthz` hits Flask (not proxied).
  - [x] Browse `/` — dashboard mounts after proxy/query-client fixes.
  - [ ] Browse `/categories`, `/transactions`, `/planning`,
    `/operations`, `/operations/runs/N` — all should render with same
    layout/colors as the React version.
  - Edit a planned category and confirm Overview's chart updates.
  - Send a request with `X-Ingress-Path: /finclaide` and confirm the
    `<base href="/finclaide/">` tag appears in the SvelteKit response.
- [ ] If smoke passes, merge `svelte-migration` → `main`. Otherwise file
      issues or fix in place on the branch.

## Soon

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
