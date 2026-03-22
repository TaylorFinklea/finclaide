from __future__ import annotations

from pathlib import Path

import pytest

from tests.workbook_builder import build_budget_workbook


def test_api_requires_bearer_token(client):
    response = client.get("/api/status")

    assert response.status_code == 401


def test_budget_import_sync_reconcile_and_summary(app_factory, auth_header, ui_headers, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    import_response = client.post("/api/budget/import", headers=auth_header)
    assert import_response.status_code == 200
    assert import_response.get_json()["row_count"] == 11

    sync_response = client.post("/api/ynab/sync", headers=auth_header)
    assert sync_response.status_code == 200
    assert sync_response.get_json()["transaction_count"] == 5

    reconcile_response = client.post("/api/reconcile", headers=auth_header)
    assert reconcile_response.status_code == 200
    assert reconcile_response.get_json()["mismatch_count"] == 0

    summary_response = client.get("/api/reports/summary?month=2026-03", headers=auth_header)
    assert summary_response.status_code == 200
    payload = summary_response.get_json()
    groups = {item["group_name"]: item for item in payload["groups"]}
    recent_dates = [item["date"] for item in payload["recent_transactions"]]

    assert payload["plan_year"] == 2026
    assert payload["overage_watch"]["categories"] == []
    assert groups["Bills"]["planned_milliunits"] == 1200000
    assert groups["Bills"]["actual_milliunits"] == 1210000
    assert any(category["status"] == "under" for category in groups["Savings"]["categories"])
    assert recent_dates == sorted(recent_dates, reverse=True)
    assert recent_dates[0] == "2026-03-07"

    tx_response = client.get(
        "/api/transactions?group=Expenses&limit=2",
        headers=auth_header,
    )
    tx_payload = tx_response.get_json()
    assert len(tx_payload["transactions"]) == 2
    assert all(item["group_name"] == "Expenses" for item in tx_payload["transactions"])

    ui_status_response = client.get("/ui-api/status")
    assert ui_status_response.status_code == 200
    ui_status_payload = ui_status_response.get_json()
    assert "latest_runs" in ui_status_payload
    assert ui_status_payload["plan_freshness"]["status"] == "fresh"
    assert ui_status_payload["actuals_provenance"]["plan_id"] == "plan-123"

    api_status_response = client.get("/api/status", headers=auth_header)
    assert api_status_response.status_code == 200
    assert "latest_runs" in api_status_response.get_json()

    ui_summary = client.get("/ui-api/summary?month=2026-03")
    assert ui_summary.status_code == 200
    assert ui_summary.get_json()["month"] == "2026-03"

    ui_transactions = client.get(
        "/ui-api/transactions?group=Expenses&q=gas&limit=1&offset=0",
    )
    ui_transactions_payload = ui_transactions.get_json()
    assert ui_transactions.status_code == 200
    assert ui_transactions_payload["total_count"] == 1
    assert ui_transactions_payload["transactions"][0]["payee_name"] == "Gas Station"

    refresh_response = client.post("/ui-api/operations/refresh-all", json={"month": "2026-03"}, headers=ui_headers)
    refresh_payload = refresh_response.get_json()
    assert refresh_response.status_code == 200
    assert "budget_import" in refresh_payload
    assert "ynab_sync" in refresh_payload
    assert refresh_payload["summary"]["month"] == "2026-03"


def test_summary_includes_overage_watch_for_repeat_overages(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    client.post("/api/reconcile", headers=auth_header)

    with services.database.connect() as connection:
        categories = {
            (row["group_name"], row["name"]): row["id"]
            for row in connection.execute("SELECT id, group_name, name FROM categories WHERE deleted = 0").fetchall()
        }
        connection.executemany(
            """
            INSERT INTO transactions(
                id,
                plan_id,
                account_id,
                date,
                payee_name,
                memo,
                cleared,
                approved,
                category_id,
                category_name,
                group_name,
                amount_milliunits,
                deleted,
                raw_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "txn-groceries-jan",
                    "plan-123",
                    "acct-checking",
                    "2026-01-05",
                    "Grocer",
                    None,
                    "cleared",
                    1,
                    categories[("Expenses", "Groceries")],
                    "Groceries",
                    "Expenses",
                    -450000,
                    0,
                    "{}",
                    "2026-03-15T12:00:00+00:00",
                ),
                (
                    "txn-groceries-feb",
                    "plan-123",
                    "acct-checking",
                    "2026-02-05",
                    "Grocer",
                    None,
                    "cleared",
                    1,
                    categories[("Expenses", "Groceries")],
                    "Groceries",
                    "Expenses",
                    -500000,
                    0,
                    "{}",
                    "2026-03-15T12:00:00+00:00",
                ),
                (
                    "txn-utilities-jan",
                    "plan-123",
                    "acct-checking",
                    "2026-01-03",
                    "Utility Co",
                    None,
                    "cleared",
                    1,
                    categories[("Bills", "Utilities")],
                    "Utilities",
                    "Bills",
                    -180000,
                    0,
                    "{}",
                    "2026-03-15T12:00:00+00:00",
                ),
                (
                    "txn-utilities-feb",
                    "plan-123",
                    "acct-checking",
                    "2026-02-03",
                    "Utility Co",
                    None,
                    "cleared",
                    1,
                    categories[("Bills", "Utilities")],
                    "Utilities",
                    "Bills",
                    -190000,
                    0,
                    "{}",
                    "2026-03-15T12:00:00+00:00",
                ),
            ],
        )

    response = client.get("/ui-api/summary?month=2026-03")
    payload = response.get_json()
    watch_categories = {
        (item["group_name"], item["category_name"]): item
        for item in payload["overage_watch"]["categories"]
    }

    assert response.status_code == 200
    assert payload["overage_watch"]["analysis_start_month"] == "2026-01"
    assert payload["overage_watch"]["analysis_end_month"] == "2026-02"
    assert ("Expenses", "Groceries") in watch_categories
    assert ("Bills", "Utilities") not in watch_categories
    assert watch_categories[("Expenses", "Groceries")]["suggested_monthly_milliunits"] == 475000
    assert watch_categories[("Expenses", "Groceries")]["shortfall_milliunits"] == 350000


def test_reconcile_fails_on_missing_category(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook, categories_fixture="categories.json")
    client = app.test_client()
    services = app.extensions["finclaide"]

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    with services.database.connect() as connection:
        connection.execute("DELETE FROM categories WHERE name = 'Investments'")
    reconcile_response = client.post("/api/reconcile", headers=auth_header)
    assert reconcile_response.status_code == 400
    assert "mismatches" in reconcile_response.get_json()["error"]


def test_operations_are_serialized(app_factory, auth_header):
    app = app_factory()
    client = app.test_client()
    services = app.extensions["finclaide"]

    with services.operation_lock.guard("hold-open"):
        response = client.post("/api/budget/import", headers=auth_header)

    assert response.status_code == 409


def test_ui_api_rejects_cross_origin_and_missing_header(app_factory):
    app = app_factory()
    client = app.test_client()

    forbidden = client.get("/ui-api/status", headers={"Origin": "https://example.com"})
    assert forbidden.status_code == 403

    missing_header = client.post("/ui-api/operations/import-budget", json={})
    assert missing_header.status_code == 403


def test_refresh_all_returns_partial_payload_on_reconcile_failure(app_factory, ui_headers, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook, categories_fixture="categories_missing_investments.json")
    client = app.test_client()

    response = client.post("/ui-api/operations/refresh-all", json={"month": "2026-03"}, headers=ui_headers)
    payload = response.get_json()

    assert response.status_code == 400
    assert "budget_import" in payload
    assert "ynab_sync" in payload
    assert "reconcile_error" in payload
    assert payload["reconcile_error"]["message"]
    assert payload["summary"]["mismatches"]


def test_failed_import_is_reflected_in_latest_runs(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", invalid_layout=True)
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    assert response.status_code == 400

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "failed"
    assert "Expected 'Stipends' header" in latest_import["details"]["error"]


def test_failed_reconcile_is_reflected_in_latest_runs(app_factory, auth_header):
    app = app_factory()
    client = app.test_client()

    response = client.post("/api/reconcile", headers=auth_header)
    assert response.status_code == 400

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_reconcile = status_payload["latest_runs"]["reconcile"]
    assert latest_reconcile["status"] == "failed"
    assert "Cannot reconcile before importing a budget." == latest_reconcile["details"]["error"]


def test_healthcheck_and_dashboard_render(app_factory):
    app = app_factory()
    client = app.test_client()

    assert client.get("/healthz").status_code == 200
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert b"<div id=\"root\"></div>" in root_response.data
