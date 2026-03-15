# Finclaide

Docker-first financial planning and reporting for a single YNAB plan plus a Google Sheets budget export.

## Runtime

1. Copy `.env.example` to `.env` and fill in the YNAB and API tokens.
2. Confirm `BUDGET_XLSX_HOST_PATH` points at the exported workbook on the host.
3. Run `make build`.
4. Run `make up`.

The Dash UI is available at `http://localhost:8050/` and the private JSON API is available under `http://localhost:8050/api/*`.

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

Run the full test suite in Docker:

```bash
make test
```
