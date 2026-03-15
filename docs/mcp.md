# Finclaide MCP

Finclaide includes a host-launched stdio MCP server that talks to the running Dockerized app over the private HTTP API.

## What It Uses

- Docker app: `http://127.0.0.1:8050`
- API base: `http://127.0.0.1:8050/api`
- Auth: `FINCLAIDE_API_TOKEN`
- MCP command: `finclaide-mcp`
- Module fallback: `python -m finclaide.mcp_server`

The MCP server does not read SQLite directly and does not talk to YNAB directly.

## Local Setup

From the repo root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
docker compose up --build -d
```

The MCP server reads `.env` automatically when launched from this repository.

Optional overrides:

```bash
export FINCLAIDE_API_BASE_URL="http://127.0.0.1:8050/api"
export FINCLAIDE_HEALTH_URL="http://127.0.0.1:8050/healthz"
```

## Finclaide MCP Tools

Finance tools:

- `get_status`
- `get_summary`
- `list_transactions`
- `import_budget`
- `sync_ynab`
- `reconcile`
- `refresh_all`

Mirror tools:

- `api_get_status`
- `api_post_budget_import`
- `api_post_ynab_sync`
- `api_post_reconcile`
- `api_get_reports_summary`
- `api_get_transactions`

Resources:

- `finclaide://status`
- `finclaide://summary/current`
- `finclaide://summary/{month}`
- `finclaide://reconciliation/latest`
- `finclaide://transactions/recent`
- `finclaide://transactions/{since}/{until}/{group}/{category}/{limit}`
  Use `_` for omitted path segments.

Prompts:

- `monthly_review`
- `investigate_mismatches`
- `spending_check`

## Codex Setup

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.finclaide]
command = "/Users/tfinklea/git/finclaide/.venv/bin/finclaide-mcp"
cwd = "/Users/tfinklea/git/finclaide"
```

If you prefer the module form:

```toml
[mcp_servers.finclaide]
command = "/Users/tfinklea/git/finclaide/.venv/bin/python"
args = ["-m", "finclaide.mcp_server"]
cwd = "/Users/tfinklea/git/finclaide"
```

## Claude Desktop Setup

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finclaide": {
      "command": "/Users/tfinklea/git/finclaide/.venv/bin/finclaide-mcp",
      "cwd": "/Users/tfinklea/git/finclaide"
    }
  }
}
```

Module form:

```json
{
  "mcpServers": {
    "finclaide": {
      "command": "/Users/tfinklea/git/finclaide/.venv/bin/python",
      "args": ["-m", "finclaide.mcp_server"],
      "cwd": "/Users/tfinklea/git/finclaide"
    }
  }
}
```

## Operating Notes

- Start with `get_status` or `get_summary`.
- Use `refresh_all` when you want the latest import, sync, and reconcile cycle.
- The server surfaces API failures directly. Reconciliation mismatches are real data issues, not warnings to ignore.
- Money values remain integer milliunits.
