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
            "Finclaide is a personal finance assistant. All monetary values are integer milliunits "
            "(divide by 1000 for dollars). Start with health_check() for general questions. "
            "Use get_summary(month) for plan-vs-actual. Use compare_months, spending_trends, "
            "and detect_anomalies for analysis. Use budget_recommendations and year_end_projection "
            "for planning. Data comes from YNAB (actuals) and an Excel workbook (plan). "
            "Call refresh_all() if data seems stale. Never infer financial data — always query."
        ),
    )

    def require_health() -> None:
        api_client.check_health()

    # ------------------------------------------------------------------
    # Core tools (7)
    # ------------------------------------------------------------------

    @server.tool(
        name="get_status",
        description="Get Finclaide runtime and sync status including last import, sync, and reconcile timestamps.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_status() -> dict[str, Any]:
        require_health()
        return api_client.get_status()

    @server.tool(
        name="get_summary",
        description=(
            "Get plan-vs-actual finance summary for a month (YYYY-MM format). Returns groups with "
            "categories showing planned, actual, variance, balance, and status. Also includes "
            "overage watch, mismatches, and recent transactions."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_summary(month: str | None = None) -> dict[str, Any]:
        require_health()
        return api_client.get_summary(month=month)

    @server.tool(
        name="list_transactions",
        description=(
            "List transactions with optional date, group, category, and limit filters. "
            "Use this to drill into specific spending after identifying issues with other tools."
        ),
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
        description="Import the mounted workbook into Finclaide. Replaces the current baseline plan.",
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

    # ------------------------------------------------------------------
    # Analytical tools (6)
    # ------------------------------------------------------------------

    @server.tool(
        name="compare_months",
        description=(
            "Compare spending between two months. Returns per-category spending for both months "
            "with absolute and percentage deltas. Use this to answer questions like 'why did "
            "spending change between January and February' or 'what's different this month vs "
            "last month'. Parameters: month_a and month_b in YYYY-MM format."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def compare_months(month_a: str, month_b: str) -> dict[str, Any]:
        require_health()
        return api_client.get_compare_months(month_a, month_b)

    @server.tool(
        name="spending_trends",
        description=(
            "Get monthly spending trends over N months, optionally filtered by group or category. "
            "Returns time series with average, min, max, trend direction, and volatility per "
            "category. Use this for questions like 'show me grocery spending trends' or "
            "'what categories are increasing'. Defaults to 6 months lookback."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def spending_trends(
        months: int = 6,
        group: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        require_health()
        return api_client.get_spending_trends(
            months=months,
            group_name=group,
            category_name=category,
        )

    @server.tool(
        name="year_end_projection",
        description=(
            "Project year-end spending based on actual run rate for completed months and plan "
            "for remaining months. Returns per-category projected totals vs annual plan with "
            "variances. Use this for 'am I on track for the year' or 'what will my total "
            "spending be'."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def year_end_projection(as_of_month: str | None = None) -> dict[str, Any]:
        require_health()
        return api_client.get_year_end_projection(as_of_month=as_of_month)

    @server.tool(
        name="detect_anomalies",
        description=(
            "Find unusual transactions and spending spikes using statistical deviation. "
            "Returns individual transactions and category-months that exceed the threshold "
            "(default 2 standard deviations from mean). Use for 'any unusual spending' or "
            "'what looks weird in my transactions'."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def detect_anomalies(months: int = 3, threshold: float = 2.0) -> dict[str, Any]:
        require_health()
        return api_client.get_anomalies(months=months, threshold=threshold)

    @server.tool(
        name="budget_recommendations",
        description=(
            "Get concrete budget optimization recommendations based on spending patterns, "
            "overage history, and year-end projections. Each recommendation includes a suggested "
            "action, reason, and projected annual impact. Use for 'what should I adjust in my "
            "budget' or 'where am I wasting money'."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def budget_recommendations() -> dict[str, Any]:
        require_health()
        return api_client.get_recommendations()

    @server.tool(
        name="health_check",
        description=(
            "Comprehensive financial health check. Returns prioritized alerts about overspending, "
            "stale data, reconciliation issues, anomalies, and year-end projection risks. "
            "This is the FIRST tool to call for a general 'how are my finances' question or "
            "periodic check-in. Severity levels: critical, warning, info."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def health_check() -> dict[str, Any]:
        require_health()
        return api_client.get_health_check()

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

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

    @server.resource(
        "finclaide://health",
        name="finclaide_health",
        description="Current financial health check with alerts.",
        mime_type="application/json",
    )
    def health_resource() -> str:
        require_health()
        return _json_text(api_client.get_health_check())

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    @server.prompt(
        name="monthly_review",
        description="Guide an AI through a comprehensive monthly review.",
    )
    def monthly_review(month: str) -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Review my finances for {month}. Follow these steps:\n"
                        "1. Call health_check() for current alerts.\n"
                        f"2. Call get_summary(month={month!r}) for plan-vs-actual by category.\n"
                        f"3. Call compare_months with {month} and the prior month to spot changes.\n"
                        "4. For any categories that are over target or flagged in overage watch, "
                        "use list_transactions to drill into the specifics.\n"
                        "5. Produce concrete findings: what's on track, what needs attention, "
                        "and any recommended budget adjustments."
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
        description="Deep-dive into spending patterns for a specific month.",
    )
    def spending_check(month: str) -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Analyze spending for {month}. Follow these steps:\n"
                        f"1. Call spending_trends(months=6) to see how {month} compares to recent history.\n"
                        f"2. Call detect_anomalies() to find unusual transactions.\n"
                        f"3. Call get_summary(month={month!r}) for plan-vs-actual context.\n"
                        "4. For flagged categories, use list_transactions with targeted filters.\n"
                        "5. Report: major overages, anomalous transactions, and categories trending up."
                    ),
                ),
            )
        ]

    @server.prompt(
        name="budget_tune_up",
        description="Guide an AI through budget optimization using actual spending data.",
    )
    def budget_tune_up() -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Perform a budget tune-up. Follow these steps:\n"
                        "1. Call budget_recommendations() to see suggested adjustments.\n"
                        "2. Call year_end_projection() to understand the full-year impact.\n"
                        "3. For each recommendation, call spending_trends(category=...) to validate the pattern.\n"
                        "4. Produce a concrete list of budget line items to change, with dollar amounts "
                        "and justification for each change."
                    ),
                ),
            )
        ]

    @server.prompt(
        name="periodic_check",
        description="Quick proactive check for issues — ideal for daily/weekly automated runs.",
    )
    def periodic_check() -> list[PromptMessage]:
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Run a periodic finance check. Follow these steps:\n"
                        "1. Call health_check() first.\n"
                        "2. If data is stale (sync > 24h), call refresh_all().\n"
                        "3. Report any critical or warning alerts with context.\n"
                        "4. If anomalies are flagged, drill into the specific transactions.\n"
                        "5. Keep the report concise — only surface items that need attention."
                    ),
                ),
            )
        ]

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
