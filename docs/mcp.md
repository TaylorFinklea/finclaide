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

Core tools:

- `get_status` — runtime and sync status
- `get_summary` — plan-vs-actual for a month
- `list_transactions` — filtered transaction list
- `import_budget` — reload workbook into SQLite
- `sync_ynab` — pull YNAB deltas
- `reconcile` — verify budget matches YNAB
- `refresh_all` — import + sync + reconcile in one call

Analytics tools:

- `compare_months` — side-by-side spending comparison between two months
- `spending_trends` — monthly time series with trend direction and volatility
- `year_end_projection` — projected year-end spending using run rate
- `detect_anomalies` — unusual transactions and category spending spikes
- `budget_recommendations` — concrete budget adjustment suggestions
- `health_check` — comprehensive health check with prioritized alerts (call first for general questions)

Resources:

- `finclaide://status`
- `finclaide://summary/current`
- `finclaide://summary/{month}`
- `finclaide://reconciliation/latest`
- `finclaide://transactions/recent`
- `finclaide://transactions/{since}/{until}/{group}/{category}/{limit}` — use `_` for omitted segments
- `finclaide://health` — current health check with alerts

Prompts:

- `monthly_review` — guided monthly review workflow
- `investigate_mismatches` — reconciliation mismatch debugging
- `spending_check` — deep-dive into spending patterns
- `budget_tune_up` — budget optimization using actual data
- `periodic_check` — quick proactive check for daily/weekly automated runs

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

- Start with `health_check` for general questions or periodic check-ins.
- Use `get_summary(month)` for detailed plan-vs-actual by category.
- Use `compare_months`, `spending_trends`, and `detect_anomalies` for analysis.
- Use `budget_recommendations` and `year_end_projection` for planning.
- Use `refresh_all` when data seems stale.
- The server surfaces API failures directly. Reconciliation mismatches are real data issues, not warnings to ignore.
- Money values are integer milliunits (divide by 1000 for dollars).
