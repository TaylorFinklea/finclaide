from __future__ import annotations

import json
from pathlib import Path

from finclaide.config import AppConfig


def test_app_config_reads_home_assistant_options_file(monkeypatch, tmp_path: Path):
    options_path = tmp_path / "options.json"
    service_account_path = tmp_path / "google-service-account.json"
    service_account_path.write_text("{}")
    local_workbook_path = tmp_path / "Budget.xlsx"
    local_workbook_path.write_text("placeholder")
    options_path.write_text(
        json.dumps(
            {
                "ynab_access_token": "ynab-token",
                "ynab_plan_id": "plan-123",
                "api_token": "api-token",
                "budget_source": "google_sheets",
                "budget_sheet_name": "2026 Budget",
                "google_file_id": "sheet-123",
                "google_service_account_path": str(service_account_path),
                "local_workbook_path": str(local_workbook_path),
                "scheduled_refresh_enabled": True,
                "scheduled_refresh_bootstrap_on_start": False,
                "scheduled_refresh_interval_minutes": 180,
            }
        )
    )
    monkeypatch.setenv("FINCLAIDE_HOME_ASSISTANT_OPTIONS_PATH", str(options_path))

    config = AppConfig.from_env()

    assert config.ynab_access_token == "ynab-token"
    assert config.ynab_plan_id == "plan-123"
    assert config.api_token == "api-token"
    assert config.budget_source == "google_sheets"
    assert config.google_sheets_file_id == "sheet-123"
    assert config.google_service_account_path == service_account_path
    assert config.budget_xlsx == local_workbook_path
    assert config.scheduled_refresh_enabled is True
    assert config.scheduled_refresh_bootstrap_on_start is False
    assert config.scheduled_refresh_interval_minutes == 180


def test_env_values_override_home_assistant_options(monkeypatch, tmp_path: Path):
    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps({"budget_source": "local_file", "google_file_id": "sheet-from-options"}))
    monkeypatch.setenv("FINCLAIDE_HOME_ASSISTANT_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("FINCLAIDE_BUDGET_SOURCE", "remote_url")
    monkeypatch.setenv("FINCLAIDE_GOOGLE_SHEETS_FILE_ID", "sheet-from-env")

    config = AppConfig.from_env()

    assert config.budget_source == "remote_url"
    assert config.google_sheets_file_id == "sheet-from-env"
