from __future__ import annotations

from pathlib import Path

import httpx
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
    assert ui_status_payload["scheduled_refresh"]["enabled"] is False

    api_status_response = client.get("/api/status", headers=auth_header)
    assert api_status_response.status_code == 200
    assert "latest_runs" in api_status_response.get_json()

    runs_response = client.get("/api/runs?limit=5", headers=auth_header)
    assert runs_response.status_code == 200
    assert len(runs_response.get_json()["runs"]) >= 3

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


def test_run_detail_returns_full_run_for_known_id(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    runs = client.get("/api/runs?limit=10", headers=auth_header).get_json()["runs"]
    target = next(run for run in runs if run["source"] == "budget_import")

    response = client.get(f"/api/runs/{target['id']}", headers=auth_header)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == target["id"]
    assert payload["source"] == "budget_import"
    assert payload["status"] == "success"
    assert payload["details"]["row_count"] == target["details"]["row_count"]


def test_run_detail_returns_404_for_unknown_id(client, auth_header):
    response = client.get("/api/runs/999999", headers=auth_header)

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "not_found"
    assert body["error_detail"]["kind"] == "not_found"


def test_ui_api_run_detail_mirrors_api(app_factory, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers={"Authorization": "Bearer test-token"})
    runs = client.get("/ui-api/runs?limit=5").get_json()["runs"]
    target = next(run for run in runs if run["source"] == "budget_import")

    response = client.get(f"/ui-api/runs/{target['id']}")

    assert response.status_code == 200
    assert response.get_json()["id"] == target["id"]


def test_reconcile_preview_classifies_planned_categories(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    response = client.get("/api/reconcile/preview", headers=auth_header)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["counts"]["missing_in_ynab"] == 0
    assert payload["counts"]["exact"] == payload["planned_count"]
    assert ("Expenses", "Groceries") in {
        (item["group_name"], item["category_name"]) for item in payload["exact_matches"]
    }


def test_reconcile_preview_surfaces_missing_in_ynab(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(
        workbook_path=workbook,
        categories_fixture="categories_missing_investments.json",
    )
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    response = client.get("/api/reconcile/preview", headers=auth_header)

    assert response.status_code == 200
    payload = response.get_json()
    missing = {(item["group_name"], item["category_name"]) for item in payload["missing_in_ynab"]}
    assert ("Savings", "Investments") in missing
    assert payload["counts"]["missing_in_ynab"] >= 1


def test_reconcile_preview_surfaces_extra_in_ynab(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    with services.database.connect() as connection:
        connection.execute(
            """
            INSERT INTO categories(
                id, plan_id, group_id, group_name, name,
                hidden, deleted, balance_milliunits, raw_json, updated_at
            ) VALUES (
                'cat-extra', 'plan-123', 'grp-expenses', 'Expenses', 'Dining Out',
                0, 0, 0, '{}', '2026-03-15T12:00:00+00:00'
            )
            """
        )

    response = client.get("/api/reconcile/preview", headers=auth_header)

    assert response.status_code == 200
    extras = {
        (item["group_name"], item["category_name"])
        for item in response.get_json()["extra_in_ynab"]
    }
    assert ("Expenses", "Dining Out") in extras


def test_reconcile_preview_excludes_hidden_groups_and_categories(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    response = client.get("/api/reconcile/preview", headers=auth_header)

    assert response.status_code == 200
    extras = {
        (item["group_name"], item["category_name"])
        for item in response.get_json()["extra_in_ynab"]
    }
    assert ("Legacy", "Archived") not in extras
    assert not any(group == "Legacy" for group, _ in extras)


def test_reconcile_preview_requires_imported_plan(client, auth_header):
    response = client.get("/api/reconcile/preview", headers=auth_header)

    assert response.status_code == 400
    body = response.get_json()
    assert "import" in body["error"].lower()


def test_ui_api_reconcile_preview_mirrors_api(app_factory, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers={"Authorization": "Bearer test-token"})
    client.post("/api/ynab/sync", headers={"Authorization": "Bearer test-token"})

    response = client.get("/ui-api/reconcile/preview")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["counts"]["missing_in_ynab"] == 0


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


def test_budget_import_can_download_remote_workbook_export(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "RemoteBudget.xlsx")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/budget.xlsx"
        return httpx.Response(
            200,
            headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            content=workbook.read_bytes(),
        )

    app = app_factory(
        budget_source="remote_url",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        workbook_url="https://example.com/budget.xlsx",
        budget_transport=httpx.MockTransport(handler),
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["row_count"] == 11

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    assert status_payload["plan_provenance"]["source_type"] == "remote_export"
    assert status_payload["plan_provenance"]["workbook_url"] == "https://example.com/budget.xlsx"
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "success"
    assert latest_import["details"]["byte_count"] > 0


def test_failed_remote_workbook_download_is_reflected_in_latest_runs(app_factory, auth_header, tmp_path: Path):
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    app = app_factory(
        budget_source="remote_url",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        workbook_url="https://example.com/missing.xlsx",
        budget_transport=httpx.MockTransport(handler),
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    assert response.status_code == 400

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "failed"
    assert "Failed to download workbook export" in latest_import["details"]["error"]


def test_weekly_review_returns_structure_and_month_scoped_anomalies(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    client.post("/api/reconcile", headers=auth_header)

    response = client.get("/api/review/weekly?month=2026-03", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["month"] == "2026-03"
    assert payload["overall_status"] in {"healthy", "warning", "critical"}
    assert isinstance(payload["headline"], str)
    assert "blockers" in payload
    assert "changes" in payload
    assert "overages" in payload
    assert "anomalies" in payload
    assert "recommendations" in payload
    assert "supporting_metrics" in payload
    assert all(
        item["evidence"].get("date", "").startswith("2026-03")
        for item in payload["anomalies"]
    )


def test_weekly_review_warns_when_budget_and_sync_are_missing(app_factory, auth_header):
    app = app_factory()
    client = app.test_client()

    response = client.get("/api/review/weekly?month=2026-03", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["overall_status"] in {"warning", "critical"}
    assert payload["blockers"]
    blocker_kinds = {item["kind"] for item in payload["blockers"]}
    assert "no_budget_blocker" in blocker_kinds


def test_weekly_review_deemphasizes_payment_flow_recommendations(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()

    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    client.post("/api/reconcile", headers=auth_header)

    response = client.get("/api/review/weekly?month=2026-03", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    signal_classes = [item["signal_class"] for item in payload["recommendations"]]
    if "payment_flow" in signal_classes:
        assert signal_classes.index("core_spend") < signal_classes.index("payment_flow")


def test_budget_import_can_export_google_sheet_with_service_account(
    app_factory, auth_header, tmp_path: Path
):
    workbook = build_budget_workbook(tmp_path / "GoogleBudget.xlsx")
    service_account = tmp_path / "service-account.json"
    service_account.write_text('{"type":"service_account"}')

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-google-token"
        if request.url.path.endswith("/files/sheet-123"):
            assert request.url.params["fields"] == "id,name,mimeType"
            assert request.url.params["supportsAllDrives"] == "true"
            return httpx.Response(
                200,
                json={
                    "id": "sheet-123",
                    "name": "Budget",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                },
            )
        assert request.headers["Authorization"] == "Bearer test-google-token"
        assert request.url.params["mimeType"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert request.url.path.endswith("/files/sheet-123/export")
        return httpx.Response(
            200,
            headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            content=workbook.read_bytes(),
        )

    app = app_factory(
        budget_source="google_sheets",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        google_service_account_path=service_account,
        google_sheets_file_id="sheet-123",
        budget_transport=httpx.MockTransport(handler),
        budget_access_token_provider=lambda: "test-google-token",
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["row_count"] == 11

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    assert status_payload["plan_provenance"]["source_type"] == "google_sheets"
    assert status_payload["plan_provenance"]["google_sheets_file_id"] == "sheet-123"
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "success"
    assert latest_import["details"]["byte_count"] > 0


def test_budget_import_can_download_google_drive_xlsx_with_service_account(
    app_factory, auth_header, tmp_path: Path
):
    workbook = build_budget_workbook(tmp_path / "GoogleDriveBudget.xlsx")
    service_account = tmp_path / "service-account.json"
    service_account.write_text('{"type":"service_account"}')

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-google-token"
        if request.url.path.endswith("/files/sheet-123"):
            if request.url.params.get("alt") == "media":
                assert request.url.params["supportsAllDrives"] == "true"
                return httpx.Response(
                    200,
                    headers={
                        "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    },
                    content=workbook.read_bytes(),
                )
            return httpx.Response(
                200,
                json={
                    "id": "sheet-123",
                    "name": "Budget.xlsx",
                    "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                },
            )
        raise AssertionError(f"Unexpected request URL: {request.url}")

    app = app_factory(
        budget_source="google_sheets",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        google_service_account_path=service_account,
        google_sheets_file_id="sheet-123",
        budget_transport=httpx.MockTransport(handler),
        budget_access_token_provider=lambda: "test-google-token",
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["row_count"] == 11

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "success"
    assert latest_import["details"]["byte_count"] > 0
    assert latest_import["details"]["drive_file_name"] == "Budget.xlsx"


def test_google_sheets_source_requires_service_account_path(app_factory, auth_header, tmp_path: Path):
    app = app_factory(
        budget_source="google_sheets",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        google_sheets_file_id="sheet-123",
        budget_access_token_provider=lambda: "test-google-token",
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    assert response.status_code == 400
    assert "GOOGLE_SERVICE_ACCOUNT_PATH" in response.get_json()["error"]


def test_google_sheets_export_failure_is_reflected_in_latest_runs(
    app_factory, auth_header, tmp_path: Path
):
    service_account = tmp_path / "service-account.json"
    service_account.write_text('{"type":"service_account"}')

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files/sheet-123"):
            return httpx.Response(
                200,
                json={
                    "id": "sheet-123",
                    "name": "Budget",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                },
            )
        return httpx.Response(403, json={"error": "forbidden"})

    app = app_factory(
        budget_source="google_sheets",
        workbook_path=tmp_path / "DownloadedBudget.xlsx",
        google_service_account_path=service_account,
        google_sheets_file_id="sheet-123",
        budget_transport=httpx.MockTransport(handler),
        budget_access_token_provider=lambda: "test-google-token",
    )
    client = app.test_client()

    response = client.post("/api/budget/import", headers=auth_header)
    assert response.status_code == 400

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_import = status_payload["latest_runs"]["budget_import"]
    assert latest_import["status"] == "failed"
    assert "Failed to export Google Sheets workbook" in latest_import["details"]["error"]


def test_scheduled_refresh_run_is_reflected_in_status(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(
        workbook_path=workbook,
        scheduled_refresh_enabled=True,
        scheduled_refresh_bootstrap_on_start=False,
        scheduled_refresh_interval_minutes=120,
    )
    app.extensions["finclaide"].scheduled_refresh.stop()
    client = app.test_client()
    services = app.extensions["finclaide"]

    result = services.scheduled_refresh.run_once()
    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_run = status_payload["latest_runs"]["scheduled_refresh"]

    assert result["status"] == "success"
    assert status_payload["scheduled_refresh"]["enabled"] is True
    assert status_payload["scheduled_refresh"]["interval_minutes"] == 120
    assert status_payload["scheduled_refresh"]["last_status"] == "success"
    assert status_payload["scheduled_refresh"]["last_finished_at"] is not None
    assert status_payload["scheduled_refresh"]["next_run_at"] is not None
    assert latest_run["status"] == "success"
    assert latest_run["details"]["reconcile"]["mismatch_count"] == 0


def test_scheduled_refresh_failure_is_reflected_in_status(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(
        workbook_path=workbook,
        categories_fixture="categories_missing_investments.json",
        scheduled_refresh_enabled=True,
        scheduled_refresh_bootstrap_on_start=False,
    )
    app.extensions["finclaide"].scheduled_refresh.stop()
    client = app.test_client()
    services = app.extensions["finclaide"]

    result = services.scheduled_refresh.run_once()
    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_run = status_payload["latest_runs"]["scheduled_refresh"]

    assert result["status"] == "failed"
    assert "Reconciliation failed" in result["reconcile_error"]
    assert status_payload["scheduled_refresh"]["last_status"] == "failed"
    assert "Reconciliation failed" in status_payload["scheduled_refresh"]["last_error"]
    assert latest_run["status"] == "failed"
    assert "Reconciliation failed" in latest_run["details"]["reconcile_error"]


def test_scheduled_refresh_skip_is_reflected_in_status(app_factory, auth_header):
    app = app_factory(scheduled_refresh_enabled=True, scheduled_refresh_bootstrap_on_start=False)
    app.extensions["finclaide"].scheduled_refresh.stop()
    client = app.test_client()
    services = app.extensions["finclaide"]

    with services.operation_lock.guard("budget_import"):
        result = services.scheduled_refresh.run_once()

    status_payload = client.get("/api/status", headers=auth_header).get_json()
    latest_run = status_payload["latest_runs"]["scheduled_refresh"]

    assert result["status"] == "skipped"
    assert "already running" in result["error"]
    assert status_payload["scheduled_refresh"]["last_status"] == "skipped"
    assert "already running" in status_payload["scheduled_refresh"]["last_error"]
    assert latest_run["status"] == "skipped"
    assert "already running" in latest_run["details"]["error"]


def test_scheduler_bootstraps_when_no_prior_successful_runs(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(
        workbook_path=workbook,
        scheduled_refresh_enabled=True,
        scheduled_refresh_bootstrap_on_start=True,
        scheduled_refresh_interval_minutes=120,
    )
    client = app.test_client()

    for _ in range(50):
        status_payload = client.get("/api/status", headers=auth_header).get_json()
        if (
            status_payload["scheduled_refresh"]["last_status"] is not None
            and status_payload["last_ynab_sync_at"] is not None
        ):
            break
    else:
        pytest.fail("Scheduled refresh did not bootstrap on startup.")

    assert status_payload["scheduled_refresh"]["last_status"] == "success"
    assert status_payload["last_budget_import_id"] is not None
    assert status_payload["last_ynab_sync_at"] is not None


def test_healthcheck_and_dashboard_render(app_factory):
    app = app_factory()
    client = app.test_client()

    assert client.get("/healthz").status_code == 200
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert b"<div id=\"root\"></div>" in root_response.data


def test_dashboard_render_injects_ingress_base_path(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/example"})

    assert response.status_code == 200
    assert b"window.__FINCLAIDE_BASE_PATH__ = \"/api/hassio_ingress/example\"" in response.data
    assert b"<base href=\"/api/hassio_ingress/example/\">" in response.data
