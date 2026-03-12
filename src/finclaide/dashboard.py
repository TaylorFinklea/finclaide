from __future__ import annotations

from dash import Dash, dcc, html
import plotly.graph_objects as go


def create_dashboard(server, services) -> Dash:
    dash_app = Dash(
        __name__,
        server=server,
        url_base_pathname="/",
        suppress_callback_exceptions=True,
        title="Finclaide",
    )

    dash_app.layout = lambda: build_layout(services.reports.summary())
    return dash_app


def build_layout(summary: dict) -> html.Div:
    groups = summary.get("groups", [])
    mismatches = summary.get("mismatches", [])
    transactions = summary.get("recent_transactions", [])
    sync_status = summary.get("sync_status", {})
    figure = build_group_figure(groups)
    annual_categories = [
        category
        | {"group_name": group["group_name"]}
        for group in groups
        for category in group["categories"]
        if category["due_month"] is not None
    ]

    return html.Div(
        style={
            "fontFamily": "Georgia, serif",
            "padding": "32px",
            "background": "linear-gradient(180deg, #f7f3e9 0%, #fffdf8 100%)",
            "minHeight": "100vh",
            "color": "#1b2a2f",
        },
        children=[
            html.H1("Finclaide", style={"marginBottom": "8px"}),
            html.P(
                f"Month: {summary.get('month')} | Plan year: {summary.get('plan_year')}",
                style={"marginTop": 0, "color": "#47585d"},
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                    "gap": "16px",
                    "marginBottom": "24px",
                },
                children=[
                    status_card("Last budget import", sync_status.get("last_budget_import_at") or "Not imported"),
                    status_card("Last YNAB sync", sync_status.get("last_ynab_sync_at") or "Not synced"),
                    status_card("Last reconcile", sync_status.get("last_reconcile_status") or "Not run"),
                    status_card("Mismatches", str(len(mismatches))),
                ],
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "2fr 1fr",
                    "gap": "24px",
                    "alignItems": "start",
                },
                children=[
                    panel("Plan vs Actual by Group", [dcc.Graph(figure=figure, config={"displayModeBar": False})]),
                    panel("Mismatch Status", [mismatch_table(mismatches)]),
                ],
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gap": "24px",
                    "marginTop": "24px",
                },
                children=[
                    panel("Annual Funding Status", [annual_table(annual_categories)]),
                    panel("Recent Transactions", [transactions_table(transactions)]),
                ],
            ),
        ],
    )


def build_group_figure(groups: list[dict]) -> go.Figure:
    figure = go.Figure()
    figure.add_bar(
        x=[group["group_name"] for group in groups],
        y=[group["planned_milliunits"] / 1000 for group in groups],
        name="Planned",
        marker_color="#52796f",
    )
    figure.add_bar(
        x=[group["group_name"] for group in groups],
        y=[group["actual_milliunits"] / 1000 for group in groups],
        name="Actual",
        marker_color="#d95d39",
    )
    figure.update_layout(
        barmode="group",
        margin={"l": 32, "r": 16, "t": 16, "b": 40},
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend={"orientation": "h"},
        yaxis_title="USD",
    )
    return figure


def panel(title: str, children: list) -> html.Div:
    return html.Div(
        style={
            "backgroundColor": "white",
            "borderRadius": "18px",
            "padding": "20px",
            "boxShadow": "0 10px 30px rgba(27, 42, 47, 0.08)",
        },
        children=[html.H2(title, style={"fontSize": "1.1rem", "marginTop": 0})] + children,
    )


def status_card(title: str, value: str) -> html.Div:
    return html.Div(
        style={
            "backgroundColor": "#1b4332",
            "color": "#fefae0",
            "padding": "18px",
            "borderRadius": "18px",
        },
        children=[
            html.Div(title, style={"fontSize": "0.8rem", "textTransform": "uppercase", "letterSpacing": "0.08em"}),
            html.Div(value, style={"fontSize": "1rem", "marginTop": "8px"}),
        ],
    )


def mismatch_table(mismatches: list[dict]) -> html.Div:
    if not mismatches:
        return html.P("No mismatches detected.")
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse"},
        children=[
            html.Thead(html.Tr([html.Th("Group"), html.Th("Category"), html.Th("Reason")])),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(item["group_name"]),
                            html.Td(item["category_name"]),
                            html.Td(item["reason"]),
                        ]
                    )
                    for item in mismatches
                ]
            ),
        ],
    )


def annual_table(categories: list[dict]) -> html.Div:
    if not categories:
        return html.P("No annual categories available.")
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse"},
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Group"),
                        html.Th("Category"),
                        html.Th("Due"),
                        html.Th("Balance"),
                        html.Th("Status"),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(category["group_name"]),
                            html.Td(category["category_name"]),
                            html.Td(category["due_month"] or "-"),
                            html.Td(f"${category['current_balance_milliunits'] / 1000:,.2f}"),
                            html.Td(category["status"]),
                        ]
                    )
                    for category in categories
                ]
            ),
        ],
    )


def transactions_table(transactions: list[dict]) -> html.Div:
    if not transactions:
        return html.P("No transactions synced yet.")
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse"},
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Date"),
                        html.Th("Payee"),
                        html.Th("Group"),
                        html.Th("Category"),
                        html.Th("Amount"),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(transaction["date"]),
                            html.Td(transaction["payee_name"] or "-"),
                            html.Td(transaction["group_name"] or "-"),
                            html.Td(transaction["category_name"] or "-"),
                            html.Td(f"${transaction['amount_milliunits'] / 1000:,.2f}"),
                        ]
                    )
                    for transaction in transactions
                ]
            ),
        ],
    )
