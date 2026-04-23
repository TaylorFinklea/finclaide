# Current State

> Updated at the end of every work session. Read this first.

## Active Branch

`svelte-migration` — not merged to `main` yet.

## Last Session Summary

**Date**: 2026-04-23

Fixed the blank dashboard discovered during Docker smoke of the Svelte
migration. Two issues were involved:

- Flask reverse proxy forwarded browser `Accept-Encoding: ... zstd` to
  SvelteKit and stripped `Content-Encoding`, so Chrome received compressed
  asset bytes as JavaScript and failed with `SyntaxError: Invalid or
  unexpected token`. `frontend.py` now forces upstream
  `Accept-Encoding: identity`; regression assertion added.
- `+layout.svelte` created the shell status query before the
  `QueryClientProvider` context existed. The layout now passes its explicit
  `queryClient` to `createQuery`.

The Docker stack is currently running at `http://127.0.0.1:8050/`; a clean
headless Chrome session confirmed the dashboard mounts, nav is present, and
there are no runtime exceptions.

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

- Backend targeted:
  `.venv/bin/pytest tests/test_api.py::test_frontend_reverse_proxies_to_configured_url`
  — pass.
- Frontend: `npm run check` — `svelte-check` 0 errors, 0 warnings.
- Docker: `docker compose up --build -d` — pass; `GET /healthz` returns
  `{"status":"ok"}`.
- Browser smoke: clean headless Chrome loaded `/`; nav text rendered and
  runtime log was empty.

## Active Milestone

Docker root-page smoke is now passing after the fixes above. Finish the
remaining route/edit/ingress manual smoke before merging `svelte-migration`
to `main`. Then resume Phase 2.5b (versioning & rollback) on the Svelte
stack.

## Blockers

- None. Branch is review-ready pending the manual smoke.
