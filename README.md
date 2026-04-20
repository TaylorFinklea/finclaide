# Finclaide

Docker-first financial planning and reporting for a single YNAB plan plus a Google Sheets budget export.

## Runtime

1. Copy `.env.example` to `.env` and fill in the YNAB and API tokens.
2. Choose a budget source:
   - `local_file`: confirm `BUDGET_XLSX_HOST_PATH` points at the workbook on the host.
   - `remote_url`: set `FINCLAIDE_BUDGET_XLSX_URL`.
   - `google_sheets`: set `FINCLAIDE_BUDGET_SOURCE=google_sheets`, `FINCLAIDE_GOOGLE_SHEETS_FILE_ID`, and `GOOGLE_SERVICE_ACCOUNT_HOST_PATH` to a service-account JSON file shared on the sheet.
3. Run `make build`.
4. Run `make up`.

If you want Finclaide to refresh the planning workbook automatically instead of relying on a manually downloaded file, set:

- `FINCLAIDE_BUDGET_SOURCE` to `remote_url` or `google_sheets`
- `FINCLAIDE_BUDGET_XLSX_URL` to a direct `.xlsx` export URL for `remote_url`
- `FINCLAIDE_GOOGLE_SHEETS_FILE_ID` and `GOOGLE_SERVICE_ACCOUNT_HOST_PATH` for `google_sheets`
- optionally `FINCLAIDE_BUDGET_XLSX_DOWNLOAD_PATH` to control where the downloaded workbook is cached locally
- `FINCLAIDE_SCHEDULED_REFRESH_ENABLED=true` to run automatic import, YNAB sync, and reconcile cycles
- `FINCLAIDE_SCHEDULED_REFRESH_BOOTSTRAP_ON_START=true` to run one startup refresh if the database has never had a successful import/sync
- optionally `FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES=360` to control the refresh cadence

When `FINCLAIDE_BUDGET_SOURCE=google_sheets`, budget import exports the spreadsheet through Google Drive as `.xlsx` using the mounted service account and then runs the normal deterministic importer against that download.

When `FINCLAIDE_BUDGET_SOURCE=remote_url`, budget import fetches the remote workbook export first and then runs the normal deterministic importer against the downloaded file.

When scheduled refresh is enabled, Finclaide records the outcome of each automatic `import -> sync -> reconcile` run in the same run history surfaced by `/api/status` and the dashboard Operations page.

The SvelteKit dashboard is available at `http://localhost:8050/`, the browser-safe UI API is available under `http://localhost:8050/ui-api/*`, and the private external API remains available under `http://localhost:8050/api/*`.

Architecture: Flask runs in the `app` container and reverse-proxies non-API paths to the `web` container, which runs the SvelteKit Node server (`adapter-node`). Both services share the same browser-visible origin (port 8050), so the same-origin gate on `/ui-api/*` keeps working unchanged. The SvelteKit container is internal-only.

## Home Assistant Add-on

The repository now includes a Home Assistant add-on scaffold under [addons/finclaide](addons/finclaide). The add-on is designed for ingress-first deployment, stores runtime state in the add-on data volume, and reads Google service account credentials or local workbook files from the add-on config volume.

See [addons/finclaide/DOCS.md](addons/finclaide/DOCS.md) for setup details and [repository.yaml](repository.yaml) for the add-on repository entry.

## Frontend Development

The production setup runs SvelteKit (`adapter-node`) as a separate Docker service that Flask reverse-proxies to. For local UI development, run the backend in Docker and start the SvelteKit dev server on the host:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/ui-api/*`, `/api/*`, and `/healthz` to `http://127.0.0.1:8050`. Open the dev UI directly at `http://localhost:5173`.

For type-check / build / test:

```bash
npm run check    # svelte-check
npm run build    # adapter-node output to build/
npm test         # vitest
```

## MCP Server

Finclaide also includes a host-launched stdio MCP server for local AI clients. It talks to the running Docker app over the private HTTP API and does not access SQLite directly.

Setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
docker compose up --build -d
```

Then launch either:

```bash
.venv/bin/finclaide-mcp
```

or:

```bash
.venv/bin/python -m finclaide.mcp_server
```

See [docs/mcp.md](docs/mcp.md) for Codex and Claude Desktop configuration examples plus the full MCP surface.

## Product Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the current multi-phase product roadmap and product direction.

## Tests

Run backend tests in Docker:

```bash
make test
```

Run frontend tests on the host:

```bash
make frontend-test
```
