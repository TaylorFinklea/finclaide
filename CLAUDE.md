# CLAUDE.md

## Session Workflow

Handoff state lives in `.docs/ai/` — see global `~/CLAUDE.md` for the standard workflow. Canonical roadmap with phase definitions is at `docs/roadmap.md`.

## What Finclaide Does

- Imports a baseline plan from the `2026 Budget` sheet in `Budget.xlsx`
- Syncs actual accounts, categories, and transactions from one YNAB plan
- Reconciles planned groups/categories against exact YNAB names
- Serves a React dashboard, a same-origin UI API, and a private JSON API from one Dockerized app

## Source of Truth

- YNAB owns actuals.
- The mounted workbook owns the baseline plan.
- SQLite is app state and cache, not the primary truth.
- If data disagrees, correct YNAB and re-run sync or import.

## How To Run It

Preferred:

```bash
docker compose up --build -d
```

Then use:

- Dashboard: `http://127.0.0.1:8050/`
- Health: `http://127.0.0.1:8050/healthz`
- API base: `http://127.0.0.1:8050/api`
- UI API base: `http://127.0.0.1:8050/ui-api`
- Host MCP command: `finclaide-mcp`

Config lives in `.env`. Important keys:

- `YNAB_ACCESS_TOKEN`
- `YNAB_PLAN_ID`
- `FINCLAIDE_API_TOKEN`
- `FINCLAIDE_API_BASE_URL`
- `FINCLAIDE_HEALTH_URL`
- `BUDGET_XLSX_HOST_PATH`

## How External AI Tools Should Use It

Prefer the MCP server when available for external AI use, and otherwise prefer the API over direct file or database access.

Normal flow:

1. `GET /healthz`
2. `GET /api/status`
3. `POST /api/budget/import`
4. `POST /api/ynab/sync`
5. `POST /api/reconcile`
6. Read:
   - `GET /api/reports/summary?month=YYYY-MM`
   - `GET /api/transactions?...`

All `/api/*` endpoints require:

```http
Authorization: Bearer <FINCLAIDE_API_TOKEN>
```

Important:

- Import, sync, and reconcile are blocking calls.
- Only one such operation runs at a time.
- Report values are integer milliunits.
- `GET /api/reports/summary` is the preferred structured output for downstream skills.

## MCP

Finclaide now exposes a host-launched stdio MCP server:

- Command: `finclaide-mcp`
- Module fallback: `python -m finclaide.mcp_server`

See [docs/mcp.md](docs/mcp.md) for setup and tool details.

## Data Rules

- Only `2026 Budget` is imported in v1.
- Legacy monthly tabs are intentionally ignored.
- Category/group matching is exact.
- `Stipends` and `Savings` are regular categories for planning/reporting purposes.
- Reconciliation failures are real integrity failures, not warnings to ignore.

## Safe Operating Guidance

- Do not write directly to SQLite unless you are explicitly changing internals.
- Do not invent category aliases.
- Do not scrape the dashboard if the API can provide the same data.
- Do not mutate the mounted workbook from the container.
- Do not treat the app as multi-tenant; it is single-household and single-plan in v1.

## Repo Landmarks

- App factory: `src/finclaide/app.py`
- API: `src/finclaide/api.py`
- Analytics API: `src/finclaide/analytics_api.py`
- Analytics service: `src/finclaide/analytics.py`
- Auth: `src/finclaide/auth.py`
- UI API: `src/finclaide/ui_api.py`
- Importer: `src/finclaide/budget_sheet.py`
- YNAB client: `src/finclaide/ynab.py`
- Reports/reconcile: `src/finclaide/services.py`
- React dashboard: `frontend/`
- Tests: `tests/`

## Verification

Preferred:

```bash
make test
```

Fallback:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install '.[dev]'
pytest
```

If you change parsing, money handling, reconciliation, or API responses, update or add deterministic tests in the same change.
