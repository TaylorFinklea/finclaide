# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main` — `svelte-migration` fast-forwarded in on 2026-04-24 (tip
`b39b0ed`). Branch `svelte-migration` still exists locally and is
identical to `main`; safe to delete once origin is pushed.

## Last Session Summary

**Date**: 2026-04-25 (Phase 2.5b — Versioning & rollback shipped end-to-end)

Built all three slices of Phase 2.5b on top of the spec at
`.docs/ai/phases/2.5b-versioning-rollback.md`:

- **Slice 1** (commit `4ea952c`) — `plan_revisions` table + index,
  widened `plans.status` CHECK to admit `'draft'/'scenario'` (with shadow-
  table migration for existing installs, run before SCHEMA_SQL so the
  view recreates against the migrated table), PlanService instrumentation
  on every write path (post-change snapshot stored as JSON, summary
  composed from the diff), `restore_revision` / `list_revisions` /
  `get_revision`, retention prune (last 50 OR last 7 days). 14 new
  pytest cases.
- **Slice 2** (commit `39cccd1`) — three endpoints on `/api/*` and
  `/ui-api/*` (list, detail, restore). Restore wraps
  `operation_lock.guard("plan_restore")` so it 409s during import/sync.
  Importer hook: `BudgetImporter._mirror_into_plan_model` now snapshots
  the about-to-be-archived plan as `source='importer'` tagged with the
  new plan_id, closing the lost-edit window. 9 new pytest cases.
  Restore re-inserts categories with fresh ids (the snapshot's original
  ids may already exist on archived plans whose `plan_categories` rows
  linger after archive).
- **Slice 3** (this commit) — `$lib/api.ts` gains revision schemas +
  `listPlanRevisions` / `getPlanRevision` / `restorePlanRevision`. New
  `frontend/src/components/plan-history-sheet.svelte` renders a right-
  side sheet with revision list, source badges, diff preview (snapshot
  vs current), and a confirm-then-restore flow that invalidates `['plan']`
  + `['summary']`. `/planning` grows a **History** button next to **Add
  row**, disabled while a budget import is busy. 3 new vitest cases at
  `frontend/src/routes/planning/history.test.ts`.

Earlier session (2026-04-24, post-merge test work):

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

- Backend: `pytest` — 124/124 pass (was 101 pre-Phase-2.5b; +23 new
  cases across `test_plan_revisions`, `test_api`, `test_budget_import`).
- Frontend: `npm run check` — `svelte-check` 0/0; `npx vitest run` —
  31/31 (was 28 pre-history-sheet; +3 new in
  `routes/planning/history.test.ts`).
- Docker / browser smoke not re-run for 2.5b — Slice 3 UI verified
  through vitest only. Worth doing a manual `docker compose` smoke
  before relying on the History flow in production.

## Active Milestone

Phase 2.5b (Versioning & rollback) is shipped end-to-end. Suggested
next: spec / brainstorm Phase 2.5c (what-if scenarios) — the
`'draft'/'scenario'` CHECK widening + `plan_revisions` schema we just
landed are the foundation for branching.

## Blockers

- None.
