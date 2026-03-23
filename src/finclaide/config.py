from __future__ import annotations

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
        config = cls(
            ynab_access_token=os.getenv("YNAB_ACCESS_TOKEN"),
            ynab_plan_id=os.getenv("YNAB_PLAN_ID"),
            api_token=os.getenv("FINCLAIDE_API_TOKEN"),
            db_path=Path(os.getenv("FINCLAIDE_DB_PATH", "/data/finclaide.db")),
            budget_source=os.getenv("FINCLAIDE_BUDGET_SOURCE", "").strip().lower()
            or _default_budget_source(),
            budget_xlsx=Path(os.getenv("FINCLAIDE_BUDGET_XLSX", "/input/Budget.xlsx")),
            budget_xlsx_url=os.getenv("FINCLAIDE_BUDGET_XLSX_URL"),
            budget_xlsx_download_path=(
                Path(download_path)
                if (download_path := os.getenv("FINCLAIDE_BUDGET_XLSX_DOWNLOAD_PATH"))
                else None
            ),
            google_service_account_path=(
                Path(service_account_path)
                if (service_account_path := os.getenv("FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH"))
                else None
            ),
            google_sheets_file_id=os.getenv("FINCLAIDE_GOOGLE_SHEETS_FILE_ID"),
            scheduled_refresh_enabled=os.getenv(
                "FINCLAIDE_SCHEDULED_REFRESH_ENABLED", ""
            ).lower() in {"1", "true", "yes", "on"},
            scheduled_refresh_bootstrap_on_start=os.getenv(
                "FINCLAIDE_SCHEDULED_REFRESH_BOOTSTRAP_ON_START", "true"
            ).lower() in {"1", "true", "yes", "on"},
            scheduled_refresh_interval_minutes=int(
                os.getenv("FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES", "360")
            ),
            frontend_dist=(
                Path(frontend_dist)
                if (frontend_dist := os.getenv("FINCLAIDE_FRONTEND_DIST"))
                else None
            ),
            host=os.getenv("FINCLAIDE_HOST", "0.0.0.0"),
            port=int(os.getenv("FINCLAIDE_PORT", "8050")),
        )
        if not overrides:
            return config
        return replace(config, **overrides)


def _default_budget_source() -> str:
    if os.getenv("FINCLAIDE_GOOGLE_SHEETS_FILE_ID"):
        return "google_sheets"
    if os.getenv("FINCLAIDE_BUDGET_XLSX_URL"):
        return "remote_url"
    return "local_file"
