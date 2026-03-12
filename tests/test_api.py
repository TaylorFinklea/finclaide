from __future__ import annotations

from pathlib import Path

import pytest

from tests.workbook_builder import build_budget_workbook


def test_api_requires_bearer_token(client):
    response = client.get("/api/status")

    assert response.status_code == 401


def test_budget_import_sync_reconcile_and_summary(app_factory, auth_header, tmp_path: Path):
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


def test_healthcheck_and_dashboard_render(app_factory):
    app = app_factory()
    client = app.test_client()

    assert client.get("/healthz").status_code == 200
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert b"Finclaide" in root_response.data
