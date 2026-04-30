# Finclaide Agent Guide

This repository is a Docker-first personal finance application. Prefer the host MCP server when available for external AI access, and otherwise use the running application over HTTP. Do not bypass the API unless you are changing internals or debugging a low-level issue.

## Product Rules

- YNAB is the source of truth for actuals.
- The `2026 Budget` sheet in the mounted `Budget.xlsx` workbook is the source of truth for the baseline plan.
- If YNAB and the sheet disagree, fix YNAB and re-sync. Do not “fix” discrepancies in SQLite.
- Historical workbook tabs are out of scope for v1. Only `2026 Budget` is imported.
- `Stipends` and `Savings` are treated as ordinary budget categories after income reaches the bank account.
- Data integrity is strict by design. Exact group/category name matches matter.

## Runtime

- Main service: `docker compose up --build -d`
- Dashboard: `http://127.0.0.1:8050/`
- Health check: `GET /healthz`
- API base: `http://127.0.0.1:8050/api`
- UI API base: `http://127.0.0.1:8050/ui-api`
- Host MCP command: `finclaide-mcp`
- API auth: `Authorization: Bearer $FINCLAIDE_API_TOKEN`
- Persistent state: Docker volume mounted at `/data`
- Workbook mount inside container: `/input/Budget.xlsx`

Use `.env` for local runtime configuration. Required values:

- `YNAB_ACCESS_TOKEN`
- `YNAB_PLAN_ID`
- `FINCLAIDE_API_TOKEN`
- `FINCLAIDE_API_BASE_URL`
- `FINCLAIDE_HEALTH_URL`
- `BUDGET_XLSX_HOST_PATH`

Useful commands:

- `docker compose ps`
- `docker compose logs -f app`
- `docker compose down`
- `make test`
- `.venv/bin/finclaide-mcp`

See [docs/mcp.md](docs/mcp.md) for Codex and Claude setup examples.

## Preferred App Workflow

When using the running app for real work, do this in order:

1. Check health: `GET /healthz`
2. Check app status: `GET /api/status`
3. Import the workbook baseline: `POST /api/budget/import`
4. Sync YNAB: `POST /api/ynab/sync`
5. Reconcile exact matches: `POST /api/reconcile`
6. Read machine-facing outputs:
   - `GET /api/reports/summary?month=YYYY-MM`
   - `GET /api/transactions?since=YYYY-MM-DD&until=YYYY-MM-DD&group=...&category=...&limit=...`

If `POST /api/reconcile` fails, treat that as a real data issue. Do not create silent aliases or fuzzy mappings.

## API Contract

Core endpoints:

- `GET /healthz`
- `GET /api/status`
- `POST /api/budget/import`
- `POST /api/ynab/sync`
- `POST /api/reconcile`
- `GET /api/reports/summary?month=YYYY-MM`
- `GET /api/transactions?...`

Analytics endpoints:

- `GET /api/analytics/compare?month_a=YYYY-MM&month_b=YYYY-MM`
- `GET /api/analytics/trends?months=6&group=...&category=...`
- `GET /api/analytics/projection?as_of_month=YYYY-MM`
- `GET /api/analytics/anomalies?months=3&threshold=2.0`
- `GET /api/analytics/recommendations`
- `GET /api/analytics/aggregate?period=quarter&group=...&category=...`
- `GET /api/analytics/health`

Important behaviors:

- All `/api/*` routes require the bearer token.
- Import, sync, and reconcile are synchronous and serialized by an app lock.
- Analytics endpoints are read-only GET requests.
- Money values are integer milliunits.
- `GET /api/analytics/health` is the best starting point for general AI queries.
- `GET /api/reports/summary` is the main plan-vs-actual report.

Example:

```bash
export TOKEN="$(grep '^FINCLAIDE_API_TOKEN=' .env | cut -d= -f2-)"

curl -sS http://127.0.0.1:8050/api/status \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST http://127.0.0.1:8050/api/budget/import \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST http://127.0.0.1:8050/api/ynab/sync \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST http://127.0.0.1:8050/api/reconcile \
  -H "Authorization: Bearer $TOKEN"

curl -sS "http://127.0.0.1:8050/api/reports/summary?month=2026-03" \
  -H "Authorization: Bearer $TOKEN"

curl -sS "http://127.0.0.1:8050/api/analytics/health" \
  -H "Authorization: Bearer $TOKEN"

curl -sS "http://127.0.0.1:8050/api/analytics/compare?month_a=2026-02&month_b=2026-03" \
  -H "Authorization: Bearer $TOKEN"
```

## Development Notes

- Core app entrypoint: `src/finclaide/app.py`
- API routes: `src/finclaide/api.py`
- Analytics API: `src/finclaide/analytics_api.py`
- Analytics service: `src/finclaide/analytics.py`
- Auth: `src/finclaide/auth.py`
- Browser UI routes: `src/finclaide/ui_api.py`
- Workbook importer: `src/finclaide/budget_sheet.py`
- YNAB wrapper: `src/finclaide/ynab.py`
- Reconciliation and reports: `src/finclaide/services.py`
- React dashboard: `frontend/`

When changing importer behavior:

- Preserve deterministic parsing.
- Keep tests for workbook parsing exhaustive and explicit.
- Do not add fuzzy matching, heuristics, or silent coercions for categories/groups.

When changing API behavior:

- Keep the API machine-friendly and stable.
- Prefer explicit JSON outputs over CLI-oriented text.
- Update tests first or alongside the behavior change.
- Keep `/api/*` token-protected for external clients.
- Keep `/ui-api/*` same-origin for the browser dashboard.

## Safe Operating Guidance

- Do not write directly to SQLite unless you are explicitly changing internals.
- Do not invent category aliases.
- Do not scrape the dashboard if the API can provide the same data.
- Do not mutate the mounted workbook from the container.
- Do not treat the app as multi-tenant; it is single-household and single-plan in v1.

## Testing

- Primary verification: `make test`
- Local fallback if Docker is unavailable:
  - `python3 -m venv .venv`
  - `. .venv/bin/activate`
  - `python -m pip install '.[dev]'`
  - `pytest`

Do not merge parser, reconciliation, or money-handling changes without deterministic tests.
