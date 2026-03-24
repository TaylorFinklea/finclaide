from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    ynab_access_token: str | None
    ynab_plan_id: str | None
    api_token: str | None
    db_path: Path
    budget_source: str
    budget_xlsx: Path
    budget_xlsx_url: str | None
    budget_xlsx_download_path: Path | None
    google_service_account_path: Path | None
    google_sheets_file_id: str | None
    scheduled_refresh_enabled: bool
    scheduled_refresh_bootstrap_on_start: bool
    scheduled_refresh_interval_minutes: int
    host: str
    port: int
    frontend_dist: Path | None = None
    budget_sheet_name: str = "2026 Budget"

    @classmethod
    def from_env(cls, overrides: dict[str, Any] | None = None) -> "AppConfig":
        addon_options = _load_home_assistant_options()
        config = cls(
            ynab_access_token=_env_or_option("YNAB_ACCESS_TOKEN", addon_options, "ynab_access_token"),
            ynab_plan_id=_env_or_option("YNAB_PLAN_ID", addon_options, "ynab_plan_id"),
            api_token=_env_or_option("FINCLAIDE_API_TOKEN", addon_options, "api_token"),
            db_path=Path(os.getenv("FINCLAIDE_DB_PATH", "/data/finclaide.db")),
            budget_source=(
                _env_or_option("FINCLAIDE_BUDGET_SOURCE", addon_options, "budget_source", "")
                .strip()
                .lower()
                or _default_budget_source(addon_options)
            ),
            budget_xlsx=Path(
                _env_or_option("FINCLAIDE_BUDGET_XLSX", addon_options, "local_workbook_path", "/input/Budget.xlsx")
            ),
            budget_xlsx_url=_env_or_option("FINCLAIDE_BUDGET_XLSX_URL", addon_options, "remote_workbook_url"),
            budget_xlsx_download_path=(
                Path(download_path)
                if (download_path := _env_or_option(
                    "FINCLAIDE_BUDGET_XLSX_DOWNLOAD_PATH",
                    addon_options,
                    "budget_xlsx_download_path",
                ))
                else None
            ),
            google_service_account_path=(
                Path(service_account_path)
                if (service_account_path := _env_or_option(
                    "FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH",
                    addon_options,
                    "google_service_account_path",
                ))
                else None
            ),
            google_sheets_file_id=_env_or_option(
                "FINCLAIDE_GOOGLE_SHEETS_FILE_ID",
                addon_options,
                "google_file_id",
            ),
            scheduled_refresh_enabled=_bool_env_or_option(
                "FINCLAIDE_SCHEDULED_REFRESH_ENABLED",
                addon_options,
                "scheduled_refresh_enabled",
                default=False,
            ),
            scheduled_refresh_bootstrap_on_start=_bool_env_or_option(
                "FINCLAIDE_SCHEDULED_REFRESH_BOOTSTRAP_ON_START",
                addon_options,
                "scheduled_refresh_bootstrap_on_start",
                default=True,
            ),
            scheduled_refresh_interval_minutes=int(
                _env_or_option(
                    "FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES",
                    addon_options,
                    "scheduled_refresh_interval_minutes",
                    "360",
                )
            ),
            frontend_dist=(
                Path(frontend_dist)
                if (frontend_dist := os.getenv("FINCLAIDE_FRONTEND_DIST"))
                else None
            ),
            host=os.getenv("FINCLAIDE_HOST", "0.0.0.0"),
            port=int(os.getenv("FINCLAIDE_PORT", "8050")),
            budget_sheet_name=_env_or_option(
                "FINCLAIDE_BUDGET_SHEET_NAME",
                addon_options,
                "budget_sheet_name",
                "2026 Budget",
            ),
        )
        if not overrides:
            return config
        return replace(config, **overrides)


def _load_home_assistant_options() -> dict[str, Any]:
    options_path = os.getenv("FINCLAIDE_HOME_ASSISTANT_OPTIONS_PATH")
    if not options_path:
        return {}
    try:
        payload = json.loads(Path(options_path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _env_or_option(
    env_name: str,
    addon_options: dict[str, Any],
    option_name: str,
    default: str | None = None,
) -> str | None:
    env_value = os.getenv(env_name)
    if env_value not in {None, ""}:
        return env_value
    option_value = addon_options.get(option_name)
    if option_value in {None, ""}:
        return default
    return str(option_value)


def _bool_env_or_option(
    env_name: str,
    addon_options: dict[str, Any],
    option_name: str,
    *,
    default: bool,
) -> bool:
    env_value = os.getenv(env_name)
    if env_value not in {None, ""}:
        return env_value.lower() in {"1", "true", "yes", "on"}
    option_value = addon_options.get(option_name)
    if isinstance(option_value, bool):
        return option_value
    if option_value in {None, ""}:
        return default
    return str(option_value).lower() in {"1", "true", "yes", "on"}


def _default_budget_source(addon_options: dict[str, Any]) -> str:
    if os.getenv("FINCLAIDE_GOOGLE_SHEETS_FILE_ID") or addon_options.get("google_file_id"):
        return "google_sheets"
    if os.getenv("FINCLAIDE_BUDGET_XLSX_URL") or addon_options.get("remote_workbook_url"):
        return "remote_url"
    return "local_file"
