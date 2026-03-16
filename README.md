# Finclaide

Docker-first financial planning and reporting for a single YNAB plan plus a Google Sheets budget export.

## Runtime

1. Copy `.env.example` to `.env` and fill in the YNAB and API tokens.
2. Confirm `BUDGET_XLSX_HOST_PATH` points at the exported workbook on the host.
3. Run `make build`.
4. Run `make up`.

The React dashboard is available at `http://localhost:8050/`, the browser-safe UI API is available under `http://localhost:8050/ui-api/*`, and the private external API remains available under `http://localhost:8050/api/*`.

## Frontend Development

The production container serves a built Vite SPA from Flask. For local UI development, run the backend normally and start the frontend on the host:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/ui-api/*`, `/api/*`, and `/healthz` to `http://127.0.0.1:8050`.

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

## Tests

Run backend tests in Docker:

```bash
make test
```

Run frontend tests on the host:

```bash
make frontend-test
```
