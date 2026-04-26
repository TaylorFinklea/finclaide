# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`main` — `svelte-migration` fast-forwarded in on 2026-04-24 (tip
`b39b0ed`). Branch `svelte-migration` still exists locally and is
identical to `main`; safe to delete once origin is pushed.

## Last Session Summary

**Date**: 2026-04-26 (Phase 2.5c Slice 1 — Sandbox in place)

Brainstormed Phase 2.5c (what-if scenarios) end-to-end through the
visual-companion mockups + Q&A. Locked the four-state cycle (Active /
Sandbox / Saved / Projection) with explicit transitions, and shipped
Slice 1 — Sandbox in place — in this session.

- **Schema** — added nullable `plans.label` column (the existing
  `plans.name` is `NOT NULL` and holds the sheet/budget title, so a
  separate column carries the user-facing scenario name). Two partial
  unique indexes enforce invariants: `idx_plans_one_sandbox` on
  `(status)` where `status='scenario' AND label IS NULL` (at most one
  Sandbox), and `idx_plans_saved_label_unique` on `(label)` where
  `status='scenario' AND label IS NOT NULL` (no duplicate Saved
  names). New `_migrate_plans_add_label_column` migration runs
  between `_migrate_plans_status_widen` and `executescript(SCHEMA_SQL)`,
  idempotent on fresh and already-migrated installs.
- **PlanService** — new `create_scenario(from_plan_id, label=None)`
  deep-copies plan + categories with fresh ids; passes label
  through. `commit_scenario(scenario_id)` archives the prior-active
  for the same year, snapshots both the prior-active and the new-
  active states into `plan_revisions` with `source='migration'`, and
  flips the scenario row to `status='active'` clearing the label.
  `discard_scenario(scenario_id)` is a hard delete (CASCADE handles
  categories + revisions). `list_scenarios()` returns scenario rows
  newest-first with category counts.
- **API** — five new `/ui-api/scenarios/...` routes: list, detail,
  create (POST with `from_plan_id` + optional `label`), commit
  (`operation_lock.guard("plan_commit")`), delete. Editing scenario
  categories reuses the existing `PATCH /ui-api/plan/categories/{id}`
  handler — scenarios are just plans with `status='scenario'`.
- **Frontend** — `/planning` gains a "Try a what-if" / "Continue
  sandbox" button next to History. Clicking creates (or resumes) a
  sandbox; the page enters Sandbox mode in place via a viewedScenarioId
  state + dynamic scenario plan query (writable opts pattern from the
  History sheet). Sandbox banner with Discard / Commit confirmation
  modals. Mutations invalidate `['plan']`, `['scenarios']`, and
  `['summary']`.
- **Tests** — 21 new pytest cases in `tests/test_scenarios.py` cover
  schema migration (idempotent against a 2.5b-shape legacy fixture),
  create lifecycle (sandbox vs saved, uniqueness rejections), list,
  commit (archives prior active, records both attribution and
  post-commit revisions, allows new sandbox after commit), and
  discard. Full backend suite: 146/146.

**Slice 1 commits this session:**
- (this commit) Schema migration + PlanService scenario methods +
  `/ui-api/scenarios/...` routes + `/planning` Sandbox mode UI +
  21 pytest cases.
- Spec at `docs/superpowers/specs/2026-04-26-phase-2.5c-scenarios-design.md`
  (mirrors the brainstormed plan; covers slices 2–4 framework but no
  implementation past slice 1).

**Slice 1 status:** all unit tests pass; `npm run check` 0/0; `npx
vitest run` 31/31 (no new vitest cases this slice — sandbox toggle
test deferred to slice 2 alongside the Saved-scenarios surface).
Manual smoke against `docker compose up` not yet performed for
slice 1; the backend test covers migration + lifecycle, and the
frontend renders cleanly under svelte-check.

Earlier session (2026-04-25, Phase 2.5b shipped end-to-end):

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

- Backend: `pytest` — 146/146 pass (was 124 pre-Phase-2.5c-slice-1;
  +21 in `test_scenarios.py` plus the moved file count for the
  earlier label-migration regression case).
- Frontend: `npm run check` — `svelte-check` 0/0; `npx vitest run` —
  31/31 (no new vitest in slice 1; planning page still 7/7 after
  the Sandbox-mode rewrite).
- Docker / browser smoke for 2.5c slice 1 not yet performed — covered
  by unit tests + svelte-check. Worth a manual smoke before slice 2.

## Active Milestone

Phase 2.5c (What-if scenarios) — Slice 1 (Sandbox in place) shipped.
Remaining slices per
`docs/superpowers/specs/2026-04-26-phase-2.5c-scenarios-design.md`:

- Slice 2 — Saved scenarios + `/scenarios` route (POST .../save,
  POST .../fork, list page, name modal, fork-on-edit).
- Slice 3 — Comparison view (per-category drilldown + 6mo sparklines;
  `POST /ui-api/scenarios/compare`).
- Slice 4 — Pure projection panel + projection→sandbox apply.

## Blockers

- None.
