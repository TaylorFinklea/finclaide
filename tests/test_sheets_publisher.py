from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from finclaide.budget_sheet import BudgetImporter
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.errors import ConfigError, DataIntegrityError
from finclaide.plan_service import PlanService
from finclaide.sheets_publisher import SheetsPublisher
from tests.workbook_builder import build_budget_workbook


def _publisher_with_imported_plan(
    tmp_path: Path,
    *,
    handler,
    budget_source: str = "google_sheets",
    google_sheets_file_id: str | None = "fid-123",
) -> tuple[SheetsPublisher, Database]:
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    database = Database(tmp_path / "finclaide.db")
    database.initialize()
    BudgetImporter(database).import_budget(workbook, "2026 Budget")
    config = AppConfig(
        api_token="x",
        ynab_access_token=None,
        ynab_plan_id=None,
        db_path=tmp_path / "finclaide.db",
        budget_source=budget_source,
        budget_xlsx=workbook,
        budget_xlsx_url=None,
        budget_xlsx_download_path=None,
        google_service_account_path=None,
        google_sheets_file_id=google_sheets_file_id,
        budget_sheet_name="2026 Budget",
        host="127.0.0.1",
        port=8050,
        scheduled_refresh_enabled=False,
        scheduled_refresh_bootstrap_on_start=False,
        scheduled_refresh_interval_minutes=360,
    )
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, timeout=30.0)
    publisher = SheetsPublisher(
        plan_service=PlanService(database=database),
        config=config,
        client=client,
        access_token_provider=lambda: "stub-access-token",
    )
    return publisher, database


def test_publisher_creates_new_tab_with_dated_name(tmp_path: Path):
    captured: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if request.url.path.endswith(":batchUpdate") and "values" not in request.url.path:
            captured["addSheet"] = body
            title = body["requests"][0]["addSheet"]["properties"]["title"]
            return httpx.Response(
                200,
                json={
                    "replies": [
                        {"addSheet": {"properties": {"sheetId": 7777, "title": title}}}
                    ]
                },
            )
        if "values:batchUpdate" in request.url.path:
            captured["values"] = body
            return httpx.Response(200, json={"totalUpdatedRows": 50})
        return httpx.Response(404)

    publisher, _ = _publisher_with_imported_plan(tmp_path, handler=handler)
    result = publisher.publish(now="2026-04-30T19:42:00+00:00")

    assert result.tab_id == 7777
    assert result.tab_name == "2026 Budget — published 2026-04-30 1942"
    assert result.tab_url == (
        "https://docs.google.com/spreadsheets/d/fid-123/edit#gid=7777"
    )
    assert captured["addSheet"]["requests"][0]["addSheet"]["properties"][
        "title"
    ] == result.tab_name


def test_publisher_writes_cells_in_importer_layout(tmp_path: Path):
    captured: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if request.url.path.endswith(":batchUpdate") and "values" not in request.url.path:
            return httpx.Response(
                200,
                json={
                    "replies": [
                        {"addSheet": {"properties": {"sheetId": 1, "title": body["requests"][0]["addSheet"]["properties"]["title"]}}}
                    ]
                },
            )
        if "values:batchUpdate" in request.url.path:
            captured["body"] = body
            return httpx.Response(200, json={})
        return httpx.Response(404)

    publisher, _ = _publisher_with_imported_plan(tmp_path, handler=handler)
    publisher.publish()

    body = captured["body"]
    assert body["valueInputOption"] == "USER_ENTERED"
    cells_by_range = {
        item["range"].split("!")[1]: item["values"][0][0] for item in body["data"]
    }
    # Bills group + Rent category at A2/A3, amount at B3.
    assert cells_by_range["A2"] == "Bills"
    assert cells_by_range["A3"] == "Rent"
    assert cells_by_range["B3"] == 1000.00
    # Stipends header + Savings header at row 1.
    assert cells_by_range["I1"] == "Stipends"
    assert cells_by_range["L1"] == "Savings"
    # Totals row carries =SUM formula.
    assert cells_by_range["B53"] == "=SUM(B2:B52)"


def test_publisher_handles_tab_name_collision(tmp_path: Path):
    seen_titles: list[str] = []
    success_after_attempts = 1  # second call succeeds

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if request.url.path.endswith(":batchUpdate") and "values" not in request.url.path:
            title = body["requests"][0]["addSheet"]["properties"]["title"]
            seen_titles.append(title)
            if len(seen_titles) <= success_after_attempts:
                return httpx.Response(
                    400,
                    json={"error": {"message": "A sheet with the title already exists.", "code": 400}},
                )
            return httpx.Response(
                200,
                json={"replies": [{"addSheet": {"properties": {"sheetId": 99, "title": title}}}]},
            )
        if "values:batchUpdate" in request.url.path:
            return httpx.Response(200, json={})
        return httpx.Response(404)

    publisher, _ = _publisher_with_imported_plan(tmp_path, handler=handler)
    result = publisher.publish(now="2026-04-30T19:42:00+00:00")

    assert len(seen_titles) == 2
    assert seen_titles[0] == "2026 Budget — published 2026-04-30 1942"
    assert seen_titles[1].endswith("(2)")
    assert result.tab_name == seen_titles[1]


def test_publisher_raises_when_budget_source_is_local(tmp_path: Path):
    publisher, _ = _publisher_with_imported_plan(
        tmp_path,
        handler=lambda req: httpx.Response(200, json={}),
        budget_source="local_file",
    )
    with pytest.raises(ConfigError):
        publisher.publish()


def test_publisher_raises_when_sheets_returns_500(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "internal"}})

    publisher, _ = _publisher_with_imported_plan(tmp_path, handler=handler)
    with pytest.raises(DataIntegrityError):
        publisher.publish()
