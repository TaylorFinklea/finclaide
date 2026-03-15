from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent, ToolAnnotations

from finclaide.mcp_client import FinclaideApiClient, FinclaideApiError
from finclaide.mcp_config import MCPConfig

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
OPERATIONAL = ToolAnnotations(readOnlyHint=False, idempotentHint=False, openWorldHint=False)


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _normalize_template_value(value: str) -> str | None:
    normalized = value.strip()
    return None if normalized in {"", "_", "-"} else normalized


def create_mcp_server(
    config: MCPConfig | None = None,
    *,
    api_client: FinclaideApiClient | None = None,
) -> FastMCP:
    config = config or MCPConfig.from_env()
    api_client = api_client or FinclaideApiClient(config)
    server = FastMCP(
        name="Finclaide",
        instructions=(
            "Use finance-oriented tools first. Treat the Finclaide API as the source for plan, "
            "transactions, and reconciliation state. Do not infer or mutate financial data outside the exposed tools."
        ),
    )

    def require_health() -> None:
        api_client.check_health()

    @server.tool(
        name="get_status",
        description="Get Finclaide runtime and sync status.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_status() -> dict[str, Any]:
        require_health()
        return api_client.get_status()

    @server.tool(
        name="get_summary",
        description="Get the machine-facing finance summary for a month in YYYY-MM format.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_summary(month: str | None = None) -> dict[str, Any]:
        require_health()
        return api_client.get_summary(month=month)

    @server.tool(
        name="list_transactions",
        description="List transactions with optional date, group, category, and limit filters.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def list_transactions(
        since: str | None = None,
        until: str | None = None,
        group: str | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        require_health()
        return api_client.get_transactions(
            since=since,
            until=until,
            group=group,
            category=category,
            limit=limit,
        )

    @server.tool(
        name="import_budget",
        description="Import the mounted workbook into Finclaide.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def import_budget() -> dict[str, Any]:
        require_health()
        return api_client.import_budget()

    @server.tool(
        name="sync_ynab",
        description="Sync accounts, categories, and transactions from YNAB into Finclaide.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def sync_ynab() -> dict[str, Any]:
        require_health()
        return api_client.sync_ynab()

    @server.tool(
        name="reconcile",
        description="Run strict exact-match reconciliation between the imported budget and YNAB categories.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def reconcile() -> dict[str, Any]:
        require_health()
        return api_client.reconcile()

    @server.tool(
        name="refresh_all",
        description="Run import, YNAB sync, then reconcile, and return the latest status and summary.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def refresh_all(month: str | None = None) -> dict[str, Any]:
        require_health()
        import_result = api_client.import_budget()
        sync_result = api_client.sync_ynab()
        reconcile_result: dict[str, Any] | None = None
        reconcile_error: dict[str, Any] | None = None
        try:
            reconcile_result = api_client.reconcile()
        except FinclaideApiError as error:
            reconcile_error = {"status_code": error.status_code, "payload": error.payload}
        return {
            "import_result": import_result,
            "sync_result": sync_result,
            "reconcile_result": reconcile_result,
            "reconcile_error": reconcile_error,
            "status": api_client.get_status(),
            "summary": api_client.get_summary(month=month),
        }

    @server.tool(
        name="api_get_status",
        description="Mirror tool for GET /api/status.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def api_get_status() -> dict[str, Any]:
        require_health()
        return api_client.get_status()

    @server.tool(
        name="api_post_budget_import",
        description="Mirror tool for POST /api/budget/import.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def api_post_budget_import() -> dict[str, Any]:
        require_health()
        return api_client.import_budget()

    @server.tool(
        name="api_post_ynab_sync",
        description="Mirror tool for POST /api/ynab/sync.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def api_post_ynab_sync() -> dict[str, Any]:
        require_health()
        return api_client.sync_ynab()

    @server.tool(
        name="api_post_reconcile",
        description="Mirror tool for POST /api/reconcile.",
        annotations=OPERATIONAL,
        structured_output=True,
    )
    def api_post_reconcile() -> dict[str, Any]:
        require_health()
        return api_client.reconcile()

    @server.tool(
        name="api_get_reports_summary",
        description="Mirror tool for GET /api/reports/summary.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def api_get_reports_summary(month: str | None = None) -> dict[str, Any]:
        require_health()
        return api_client.get_summary(month=month)

    @server.tool(
        name="api_get_transactions",
        description="Mirror tool for GET /api/transactions.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def api_get_transactions(
        since: str | None = None,
        until: str | None = None,
        group: str | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        require_health()
        return api_client.get_transactions(
            since=since,
            until=until,
            group=group,
            category=category,
            limit=limit,
        )

    @server.resource(
        "finclaide://status",
        name="finclaide_status",
        description="Current Finclaide runtime status.",
        mime_type="application/json",
    )
    def status_resource() -> str:
        require_health()
        return _json_text(api_client.get_status())

    @server.resource(
        "finclaide://summary/current",
        name="finclaide_summary_current",
        description="Current-month Finclaide summary.",
        mime_type="application/json",
    )
    def summary_current_resource() -> str:
        require_health()
        return _json_text(api_client.get_summary())

    @server.resource(
        "finclaide://summary/{month}",
        name="finclaide_summary",
        description="Summary for a specific month in YYYY-MM format.",
        mime_type="application/json",
    )
    def summary_resource(month: str) -> str:
        require_health()
        return _json_text(api_client.get_summary(month=month))

    @server.resource(
        "finclaide://reconciliation/latest",
        name="finclaide_reconciliation_latest",
        description="Latest reconciliation status and mismatches.",
        mime_type="application/json",
    )
    def reconciliation_latest_resource() -> str:
        require_health()
        status = api_client.get_status()
        summary = api_client.get_summary()
        payload = {
            "run_at": status.get("last_reconcile_at"),
            "status": status.get("last_reconcile_status"),
            "mismatches": summary.get("mismatches", []),
        }
        return _json_text(payload)

    @server.resource(
        "finclaide://transactions/recent",
        name="finclaide_transactions_recent",
        description="The most recent transactions from Finclaide.",
        mime_type="application/json",
    )
    def transactions_recent_resource() -> str:
        require_health()
        return _json_text(api_client.get_transactions(limit=20))

    @server.resource(
        "finclaide://transactions/{since}/{until}/{group}/{category}/{limit}",
        name="finclaide_transactions_filtered",
        description="Filtered transactions. Use '_' for omitted path segments.",
        mime_type="application/json",
    )
    def transactions_template_resource(
        since: str,
        until: str,
        group: str,
        category: str,
        limit: str,
    ) -> str:
        require_health()
        parsed_limit = int(_normalize_template_value(limit) or "50")
        payload = api_client.get_transactions(
            since=_normalize_template_value(since),
            until=_normalize_template_value(until),
            group=_normalize_template_value(group),
            category=_normalize_template_value(category),
            limit=parsed_limit,
        )
        return _json_text(payload)

    @server.prompt(
        name="monthly_review",
        description="Guide an AI through a monthly review using Finclaide data.",
    )
    def monthly_review(month: str) -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Review the Finclaide data for {month}. Start with get_summary(month={month!r}), "
                        "then inspect list_transactions for categories that are over target, underfunded yearly items, "
                        "or uncategorized spending. Produce concrete findings grounded in the returned JSON."
                    ),
                ),
            )
        ]

    @server.prompt(
        name="investigate_mismatches",
        description="Guide an AI through reconciliation mismatch investigation.",
    )
    def investigate_mismatches() -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Use get_status() and get_summary() to inspect the latest reconciliation state. "
                        "If mismatches exist, list each missing exact match and recommend the YNAB group/category "
                        "changes needed to make reconcile() pass cleanly."
                    ),
                ),
            )
        ]

    @server.prompt(
        name="spending_check",
        description="Guide an AI through transaction review for a budget month.",
    )
    def spending_check(month: str) -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Check spending for {month}. Use get_summary(month={month!r}) for plan-vs-actual context, "
                        "then use list_transactions with targeted filters to explain major overages, unusual spending, "
                        "and categories that need attention."
                    ),
                ),
            )
        ]

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
