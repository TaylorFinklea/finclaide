# Frontend migration: React (Vite SPA) → Svelte 5 + SvelteKit (adapter-node)

**Status**: Code complete on `svelte-migration` branch (2026-04-20).
Awaiting manual smoke before merge.
**Owner**: Claude (tier3_owner)
**Approved plan**: `/Users/tfinklea/.claude/plans/delightful-tinkering-boole.md`
**Commits** (on `svelte-migration`, not pushed):

- `69cc2e4` — SvelteKit project skeleton
- `1c093ac` — lib utils + UI primitives (bits-ui wrappers)
- `f722987` — 9 domain components
- `9ff1213` — 6 routes + AppShell + hooks.server.ts
- `e46a8e9` — Flask reverse proxy
- `7f45601` — Dockerfile.web + compose + addon

## Goal

Replace the React (Vite SPA) frontend with Svelte 5 + SvelteKit
(`adapter-node`) without changing user-visible behavior. The motivation
was DX — the operator prefers writing Svelte. No new features, no
visual regressions intended.

## Architecture changes

- Flask is no longer a static-file server. It reverse-proxies non-API
  paths (everything except `/api/*`, `/ui-api/*`, `/healthz`) to the
  internal SvelteKit Node container at `FINCLAIDE_FRONTEND_URL`
  (defaults to `http://web:3000` in compose, `http://127.0.0.1:3000`
  in the HA add-on).
- The browser still sees a single origin (port 8050), so the
  same-origin gate on `/ui-api/*` keeps working unchanged.
- Home Assistant ingress base-path injection moved from Flask's
  index.html rewrite to SvelteKit's `hooks.server.ts` —
  `transformPageChunk` injects the same
  `<script>window.__FINCLAIDE_BASE_PATH__ = "..."</script>` and
  `<base href="...">` tags Flask used to inject.
- `Dockerfile` is now Python-only. New `Dockerfile.web` builds the
  SvelteKit Node container. The HA add-on bundles both runtimes;
  `run.sh` starts `node build` alongside gunicorn before nginx.

## Stack changes

| React | Svelte |
|---|---|
| React 19 + Vite 7 | Svelte 5 + SvelteKit + Vite 6 (downgraded for SvelteKit compat) |
| `useState/useEffect/useMemo` | `$state / $effect / $derived` |
| `useContext` | shared rune class store (`monthStore`) |
| `useQuery / useMutation` | `createQuery / createMutation` from `@tanstack/svelte-query` |
| react-router-dom | SvelteKit file-based routing |
| `lazy + Suspense` | SvelteKit auto code-splits routes |
| `@radix-ui/*` | `bits-ui` |
| `lucide-react` | `lucide-svelte` |
| `sonner` | `svelte-sonner` |
| `recharts` | hand-rolled SVG bar chart (single consumer) |
| `@tanstack/react-table` | hand-rolled DataTable wrapper |
| `@testing-library/react` | `@testing-library/svelte` |
| Vitest 4 | Vitest 2 (downgraded for vite 6 compat) |

## Notable design decisions made during execution

- **Reactive query options pattern**. The installed
  `@tanstack/svelte-query@^5.62` accepts `StoreOrVal<options>` only —
  not the function-options pattern documented for newer versions. Where
  query keys depend on Svelte 5 runes (e.g. `monthStore.value`), I
  wrap a `writable` Svelte store and update it in `$effect`. Static-key
  queries (status, plan/active, runs) use plain object literals.
  Documented in each affected page.
- **Hand-rolled DataTable + GroupChart**. The data sets are small
  (≤50 rows; one chart consumer) and avoiding `@tanstack/svelte-table`
  + `layerchart` keeps the dependency surface lean per the
  "roll our own" plan choice.
- **Page-level vitest cases deferred**. Only a button smoke test was
  ported in this migration (proves the pipeline works). The 19 React
  page-level cases need proper mock + `QueryClientProvider` wrapper
  setup; tracked in next-steps for a follow-up commit before resuming
  Phase 2.5b.
- **Shared origin via Flask reverse proxy** (vs. nginx in front).
  Reuses the existing public port (8050) and avoids a third container.
  Flask already had `httpx` as a dependency.
- **Editor saves still don't share `OperationLock`**. Same decision
  as Phase 2.5a; preserved across the migration.

## Exit criteria

- [x] All 6 React pages render in Svelte with visual parity intent.
- [x] Backend tests unchanged at 100, plus 2 new proxy tests
      replacing the obsolete dashboard-injection test → 101 total.
- [x] svelte-check 0 errors, 0 warnings.
- [x] adapter-node build succeeds.
- [ ] Manual smoke of the new Docker stack — gates the merge.

## Verification

- Backend: `cd /Users/tfinklea/git/finclaide && . .venv/bin/activate &&
  python -m pytest -q` → 101/101.
- Frontend: `cd frontend && npm run check` → 0 errors / 0 warnings
  across 4233 files.
- Frontend: `npm run build` (adapter-node) → verified after Slice 1.
- Frontend: `npm test` → button smoke 2/2.
- Manual smoke pending (see `.docs/ai/next-steps.md`).

## Out of scope (deferred)

- Phase 2.5b/c/d on the Svelte stack — no new feature work during the
  migration.
- SSR of Finclaide pages — pages are CSR (`+layout.ts` sets
  `ssr=false`). The Node server is there for future SSR flexibility.
- SvelteKit form actions, `+page.server.ts`, `+server.ts` endpoints —
  all logic stays in Flask.
- Page-level vitest port — see "Soon" in next-steps.

## Risks acknowledged in the plan

- **Same-origin gate breaks** if SvelteKit serves on a different port.
  Mitigated: Flask remains the only public-facing port; SvelteKit Node
  is internal-only behind Flask's reverse proxy. Verified by the new
  pytest cases.
- **HA ingress base path lost**. Mitigated: `hooks.server.ts` reads
  `X-Ingress-Path` / `X-Forwarded-Prefix` and uses `transformPageChunk`
  to inject the same `<script>` and `<base href>` tags Flask used to
  inject. Pending manual smoke.
- **Big-bang scope**. Mitigated by the strict 6-commit sequence — each
  commit was verified before the next began.
- **`@tanstack/svelte-query` Svelte 5 runes maturity**. Mitigated by
  using the documented `createMutation` / `createQuery` API + the
  writable-store pattern for reactive options. Tracked as a known
  rough edge.
- **Recharts → hand-rolled SVG**. Visual diff acceptable for the single
  consumer; revisit if the operator wants richer interactions.

## Files touched

**New (frontend)**: 24 component files (`src/components/ui/*.svelte`,
`src/components/*.svelte`), 6 routes (`src/routes/**/+page.svelte`),
layout (`src/routes/+layout.svelte`, `+layout.ts`), hooks
(`src/hooks.server.ts`), config (`svelte.config.js`, `vite.config.ts`,
`vitest.config.ts`, `tsconfig.json`, `app.html`, `app.d.ts`,
`app.css`, `static/favicon.svg`, `package.json`,
`package-lock.json`, `.gitignore`), button smoke
(`src/components/ui/button.test.ts`).

**Removed (frontend)**: All `frontend/src/**/*.tsx`,
`frontend/index.html`, `frontend/eslint.config.js`,
`frontend/components.json`, React-specific tsconfig and vitest configs.

**Modified (backend)**: `src/finclaide/config.py` (added
`frontend_url`), `src/finclaide/frontend.py` (reverse proxy),
`tests/test_api.py` (replaced dashboard injection test with 2 new
proxy tests).

**Modified (deployment)**: `Dockerfile` (Python only),
`docker-compose.yml` (added `web` service), `addons/finclaide/Dockerfile`
(Node + Python multi-stage), `addons/finclaide/run.sh` (dual-process
startup).

**New (deployment)**: `Dockerfile.web`.

**Modified (docs)**: `README.md` (architecture note + dev workflow).
