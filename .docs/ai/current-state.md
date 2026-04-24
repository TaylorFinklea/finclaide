# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main` — `svelte-migration` fast-forwarded in on 2026-04-24 (tip
`b39b0ed`). Branch `svelte-migration` still exists locally and is
identical to `main`; safe to delete once origin is pushed.

## Last Session Summary

**Date**: 2026-04-24 (second pass, post-merge work)

Worked the full post-merge plan
(`/Users/tfinklea/.claude/plans/what-comes-next-concurrent-noodle.md`):

- **Phase 0** — fast-forwarded `svelte-migration` (`b39b0ed`) into
  `main`. Commit `699ad52` updates handoff docs.
- **Phase 1** — `frontend/src/hooks.server.test.ts` regression guard
  with 8 cases (ingress + forwarded headers, precedence, normalizeBasePath
  edges, explicit `</head>` vs `%sveltekit.head%` guard). Commit `406d68b`.
- **Phase 2** — Svelte test scaffolding: `$app/*` mocks,
  `QueryClientProvider` harness, fixtures ported from
  `git show 69cc2e48~1:frontend/src/test/fixtures.ts`. Commit `c267a9a`.
- **Phase 3** — 18 React page-level vitest cases ported to Svelte:
  categories (1) `d325f7f`, operations (1, plus global `svelte-sonner`
  mock) `56f8454`, overview (1) `aa6be2a`, transactions (3 — required
  vitest 2 → 3.2.4 upgrade to align Vite versions; commits `9de0cc8` +
  `581c96b`), planning (7) `4d68044`, a11y (5, via layout-harness)
  `7992b0d`. Full suite 28/28; svelte-check 0/0.
- **Phase 4** — wrote the Phase 2.5b (Versioning & rollback) spec at
  `.docs/ai/phases/2.5b-versioning-rollback.md`. Design-only;
  implementation follows as a separate phase.

Previous session (2026-04-23):

Ran the full manual smoke of `svelte-migration` through Playwright MCP +
`curl`. Four routes (`/categories`, `/transactions`, `/planning`,
`/operations`) and the run-detail view (`/operations/runs/148`) all render
with zero console errors. Plan-edit round-trip verified: bumping
`Bills › 22nd - Claude` from $200 to $201 moved the summary payload's
`groups[Bills].planned_milliunits` from 7,116,040 → 7,117,040; revert
restored baseline. GroupChart SVG (aria-label "Plan vs actual by group")
re-renders from the updated summary.

Fixed a real regression in `frontend/src/hooks.server.ts`: the ingress
base-href injection never actually fired. `transformPageChunk` was calling
`html.replace('%sveltekit.head%', …)`, but SvelteKit substitutes that
placeholder in the template before streaming, so the replace was a no-op.
Switched the marker to `</head>`. Verified with curl:
- `X-Ingress-Path: /finclaide` → emits `<base href="/finclaide/">` plus the
  `window.__FINCLAIDE_BASE_PATH__` / `__FINCLAIDE_BASE_HREF__` globals.
- No header → falls back to `<base href="/">` (basePath normalises to ``).

The prior session's pytest case only verified that the header was
forwarded through the Flask proxy — it never asserted the rewrite. Now
that the rewrite actually happens, a Node-side vitest case for
`hooks.server.ts` is queued in next-steps.

Prior migration fixes still in place:

- Flask reverse proxy forwarded browser `Accept-Encoding: ... zstd` to
  SvelteKit and stripped `Content-Encoding`, so Chrome received compressed
  asset bytes as JavaScript and failed with `SyntaxError: Invalid or
  unexpected token`. `frontend.py` now forces upstream
  `Accept-Encoding: identity`; regression assertion added.
- `+layout.svelte` created the shell status query before the
  `QueryClientProvider` context existed. The layout now passes its explicit
  `queryClient` to `createQuery`.

Prior migration commit log on `svelte-migration`:

- `69cc2e4` — Slice 1: SvelteKit project skeleton (svelte.config.js,
  vite.config.ts, app.html, app.css verbatim Tailwind tokens, placeholder
  route). Removed all React files. vite ^6 (downgraded from ^7 for
  SvelteKit compat) + vitest ^2.
- `1c093ac` — Slice 2: lib utils + UI primitives. Ported `lib/api.ts`
  (verbatim Zod schemas), `format.ts`, `runtime.ts`, `utils.ts`. New
  `lib/stores/month.svelte.ts` (Svelte 5 rune store). 23 UI primitives
  wrapping bits-ui (Dialog, Sheet, Select, Tabs) plus pure-Tailwind
  Card/Button/Badge/Input/Skeleton/Table parts. Vitest setup with
  pointer-capture stubs + `resolve.conditions: ['browser']`. button
  smoke test passes (2/2).
- `f722987` — Slice 3: 9 domain components (status-chip, freshness-chip,
  metric-card, data-table, failure-cause-card, reconcile-preview-card,
  automation-status-card, plan-category-sheet, group-chart). DataTable
  is a hand-rolled wrapper (no @tanstack/svelte-table). GroupChart is a
  hand-rolled SVG bar chart (no recharts). svelte-sonner toasts.
- `9ff1213` — Slice 4: routes + hooks. All 6 React pages ported to
  SvelteKit file-based routing. AppShell in `+layout.svelte` with nav,
  freshness chips, scheduled-refresh banner, QueryClientProvider.
  `hooks.server.ts` injects HA ingress base path via `transformPageChunk`.
  Reactive query options use the writable-store + $effect pattern since
  this version of `@tanstack/svelte-query` only accepts `StoreOrVal`.
  Page-level vitest cases deferred to a follow-up if needed.
- `e46a8e9` — Slice 5: Flask reverse proxy. `frontend.py` rewritten to
  forward non-API paths to `FINCLAIDE_FRONTEND_URL` via httpx. `config.py`
  gains `frontend_url`. Two new pytest cases for proxy behavior.
- `7f45601` — Slice 6: Docker + addon. New `Dockerfile.web` (SvelteKit
  Node container). Trimmed root `Dockerfile` (Python only). Compose adds
  `web` service. HA add-on bundles both runtimes; `run.sh` starts
  `node build` alongside gunicorn before nginx.

## Build Status

- Backend targeted: `pytest tests/test_api.py -k frontend` — 2/2 pass.
- Frontend: `npm run check` — `svelte-check` 0 errors, 0 warnings.
- Docker: `docker compose up -d --build web` — web container rebuilt after
  hook change; healthy.
- Browser smoke: Playwright MCP walked `/`, `/categories`, `/transactions`,
  `/planning`, `/operations`, `/operations/runs/148` — all render with zero
  console errors.
- Ingress smoke: curl-verified in both directions.

## Active Milestone

Phases 0–4 of the post-merge plan are complete. Active forward surface:
review + approve the Phase 2.5b spec
(`.docs/ai/phases/2.5b-versioning-rollback.md`), then start Slice 1
(schema + PlanService + tests — backend only, no UI yet).

## Blockers

- None.
