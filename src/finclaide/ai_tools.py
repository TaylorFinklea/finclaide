"""Tool definitions and dispatch for the in-app AI rail.

Every tool is a thin, read-only adapter over ``ServiceContainer``. Each accepts
a JSON-serialisable kwargs dict (the shape Anthropic's tool-use API gives us)
and returns a JSON-serialisable result. The model never gets a Python object;
it only sees the dict we return.

Operational tools (sync, import, reconcile, plan edits) are intentionally
NOT exposed — the rail is read-only in v1. The user explicitly stages and
commits any change via the regular UI.
"""

from __future__ import annotations

from datetime import UTC, datetime, date
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from finclaide.services import ServiceContainer


ToolFn = Callable[["ServiceContainer", dict[str, Any]], Any]


_MONTH_DESC = "Month in YYYY-MM format. Defaults to the current month."


# Anthropic tool-use schema: each tool is {name, description, input_schema}.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_status",
        "description": (
            "Get Finclaide runtime status — last import, sync, reconcile timestamps, plan freshness,"
            " and whether YNAB is stale. Use this first when the user asks 'is everything up to date'."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_summary",
        "description": (
            "Plan-vs-actual summary for a month. Returns groups with categories, each showing"
            " planned, actual, variance, balance, pace status. Includes recent transactions and"
            " any reconcile mismatches. Use for 'how am I doing this month' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"month": {"type": "string", "description": _MONTH_DESC}},
            "required": [],
        },
    },
    {
        "name": "get_review",
        "description": (
            "Weekly review for a month: blockers, what-changed, overages, anomalies, recommendations,"
            " and a one-line headline. Pre-computed by the same engine that powers the /review screen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"month": {"type": "string", "description": _MONTH_DESC}},
            "required": [],
        },
    },
    {
        "name": "list_transactions",
        "description": (
            "List transactions filtered by date range, group, category, payee. Use after a higher-level"
            " tool surfaces something interesting and the user asks 'show me the actual transactions'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "Inclusive YYYY-MM-DD lower bound."},
                "until": {"type": "string", "description": "Exclusive YYYY-MM-DD upper bound."},
                "group": {"type": "string", "description": "Match group_name exactly."},
                "category": {"type": "string", "description": "Match category_name exactly."},
                "limit": {"type": "integer", "description": "Max rows (default 50, max 500)."},
            },
            "required": [],
        },
    },
    {
        "name": "get_projection",
        "description": (
            "Year-end projection. Returns projected total spend by category/group based on month-to-date"
            " pace and trailing trend. Use for 'will I end the year over budget' or 'what's my projected"
            " close' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"as_of_month": {"type": "string", "description": _MONTH_DESC}},
            "required": [],
        },
    },
    {
        "name": "get_pace",
        "description": (
            "Month-to-date pace — actual versus calendar-proportional plan. Use for 'am I ahead or"
            " behind for this month' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"month": {"type": "string", "description": _MONTH_DESC}},
            "required": [],
        },
    },
    {
        "name": "get_cashflow",
        "description": (
            "Cash-flow timeline: monthly inflow vs outflow vs net over the last N months. Use for"
            " 'how is my cash flow trending' or 'what's my MoM net' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "Window size (default 12, max 36)."},
                "as_of_month": {"type": "string", "description": _MONTH_DESC},
            },
            "required": [],
        },
    },
    {
        "name": "get_rebalance_prompts",
        "description": (
            "Suggested rebalances — pairs of categories where moving budget from one to another would"
            " keep total monthly spend flat while reducing overage risk. Use when the user asks 'how"
            " should I adjust the plan' or after they say a category is overrunning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "History window (default 12)."},
                "as_of_month": {"type": "string", "description": _MONTH_DESC},
            },
            "required": [],
        },
    },
    {
        "name": "get_anomalies",
        "description": (
            "Categories whose recent spend is anomalous against their trailing average (z-score based)."
            " Use for 'anything weird this month' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "Trail window (default 3)."},
                "threshold": {"type": "number", "description": "Sigma threshold (default 2.0)."},
                "as_of_month": {"type": "string", "description": _MONTH_DESC},
            },
            "required": [],
        },
    },
    {
        "name": "get_recommendations",
        "description": (
            "Budget recommendations: which categories are projected to end over/under target, sorted"
            " by impact. Pairs well with get_rebalance_prompts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"as_of_month": {"type": "string", "description": _MONTH_DESC}},
            "required": [],
        },
    },
    {
        "name": "compare_months",
        "description": (
            "Compare two months category-by-category. Returns deltas and percent changes."
            " Use for 'how does this month compare to last' or 'lifestyle vs last quarter' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "month_a": {"type": "string", "description": "Baseline month, YYYY-MM."},
                "month_b": {"type": "string", "description": "Comparison month, YYYY-MM."},
            },
            "required": ["month_a", "month_b"],
        },
    },
    {
        "name": "get_spending_trends",
        "description": (
            "Per-category spending trend over the last N months. Use to surface gradual creep or"
            " seasonality — not single-month anomalies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "Window size (default 6)."},
                "group": {"type": "string"},
                "category": {"type": "string"},
                "as_of_month": {"type": "string", "description": _MONTH_DESC},
            },
            "required": [],
        },
    },
    {
        "name": "get_financial_health",
        "description": (
            "High-level health snapshot: cash on hand, monthly burn, runway months, savings rate."
            " Use for 'how healthy am I overall' questions."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_scenarios",
        "description": (
            "List in-progress plan scenarios (sandboxed drafts of the plan). Each has an id you can"
            " pass to get_scenario_compare."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_scenario_compare",
        "description": (
            "Diff a scenario against the active plan: per-category before/after, net monthly change,"
            " and projected impact on year-end close."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"scenario_id": {"type": "integer"}},
            "required": ["scenario_id"],
        },
    },
    {
        "name": "list_runs",
        "description": (
            "Recent operational runs (imports, YNAB syncs, reconciles) with status and durations."
            " Use to diagnose 'why is the data stale' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max rows (default 20)."}},
            "required": [],
        },
    },
]


def _get_status(container: "ServiceContainer", _: dict[str, Any]) -> Any:
    return container.reports.status(include_recent_runs=True)


def _get_summary(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.reports.summary(month=args.get("month"))


def _get_review(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.review.weekly(month=args.get("month"))


def _list_transactions(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    limit = min(int(args.get("limit") or 50), 500)
    return container.reports.transactions(
        since=args.get("since"),
        until=args.get("until"),
        group_name=args.get("group"),
        category_name=args.get("category"),
        limit=limit,
    )


def _get_projection(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.year_end_projection(as_of_month=args.get("as_of_month"))


def _get_pace(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.month_pace(month=args.get("month"))


def _get_cashflow(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    months = min(int(args.get("months") or 12), 36)
    return container.analytics.cash_flow_timeline(
        months=months,
        as_of_month=args.get("as_of_month"),
    )


def _get_rebalance_prompts(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.cash_flow_rebalance_prompts(
        months=int(args.get("months") or 12),
        as_of_month=args.get("as_of_month"),
    )


def _get_anomalies(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.detect_anomalies(
        months=int(args.get("months") or 3),
        threshold_sigma=float(args.get("threshold") or 2.0),
        as_of_month=args.get("as_of_month"),
    )


def _get_recommendations(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.budget_recommendations(as_of_month=args.get("as_of_month"))


def _compare_months(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.compare_months(args["month_a"], args["month_b"])


def _get_spending_trends(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.analytics.spending_trends(
        months=int(args.get("months") or 6),
        group_name=args.get("group"),
        category_name=args.get("category"),
        as_of_month=args.get("as_of_month"),
    )


def _get_financial_health(container: "ServiceContainer", _: dict[str, Any]) -> Any:
    return container.analytics.financial_health_check()


def _list_scenarios(container: "ServiceContainer", _: dict[str, Any]) -> Any:
    return {"scenarios": container.plan.list_scenarios()}


def _get_scenario_compare(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    return container.plan.compare_scenario(int(args["scenario_id"]))


def _list_runs(container: "ServiceContainer", args: dict[str, Any]) -> Any:
    limit = min(int(args.get("limit") or 20), 200)
    return container.reports.runs(limit=limit)


DISPATCH: dict[str, ToolFn] = {
    "get_status": _get_status,
    "get_summary": _get_summary,
    "get_review": _get_review,
    "list_transactions": _list_transactions,
    "get_projection": _get_projection,
    "get_pace": _get_pace,
    "get_cashflow": _get_cashflow,
    "get_rebalance_prompts": _get_rebalance_prompts,
    "get_anomalies": _get_anomalies,
    "get_recommendations": _get_recommendations,
    "compare_months": _compare_months,
    "get_spending_trends": _get_spending_trends,
    "get_financial_health": _get_financial_health,
    "list_scenarios": _list_scenarios,
    "get_scenario_compare": _get_scenario_compare,
    "list_runs": _list_runs,
}


def dispatch(container: "ServiceContainer", name: str, args: dict[str, Any]) -> Any:
    """Resolve a tool call. Raises KeyError if the tool name is unknown."""
    return DISPATCH[name](container, args or {})


def current_month_label(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return moment.strftime("%Y-%m")


def today_label(today: date | None = None) -> str:
    moment = today or datetime.now(UTC).date()
    return moment.strftime("%Y-%m-%d")
