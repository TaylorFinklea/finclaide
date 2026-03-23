from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from finclaide.config import AppConfig
from finclaide.database import utc_now
from finclaide.errors import ConfigError, DataIntegrityError

GOOGLE_DRIVE_EXPORT_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_SHEETS_EXPORT_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

AccessTokenProvider = Callable[[], str]


@dataclass
class BudgetWorkbookSource:
    config: AppConfig
    client: httpx.Client
    access_token_provider: AccessTokenProvider | None = None

    def describe(self) -> dict[str, Any]:
        if self.config.budget_source == "google_sheets":
            return {
                "source_type": "google_sheets",
                "google_sheets_file_id": self.config.google_sheets_file_id,
                "google_service_account_path": str(self.config.google_service_account_path)
                if self.config.google_service_account_path
                else None,
                "workbook_path": str(self.download_path()),
                "sheet_name": self.config.budget_sheet_name,
            }
        if self.config.budget_source == "remote_url":
            return {
                "source_type": "remote_export",
                "workbook_url": self.config.budget_xlsx_url,
                "workbook_path": str(self.download_path()),
                "sheet_name": self.config.budget_sheet_name,
            }
        return {
            "source_type": "local_workbook",
            "workbook_path": str(self.config.budget_xlsx),
            "sheet_name": self.config.budget_sheet_name,
        }

    def current_path(self) -> Path:
        if self.config.budget_source in {"google_sheets", "remote_url"}:
            return self.download_path()
        return self.config.budget_xlsx

    def prepare(self) -> dict[str, Any]:
        details = self.describe()
        if self.config.budget_source == "local_file":
            return details
        if self.config.budget_source == "remote_url":
            return self._download(
                self.config.budget_xlsx_url,
                details=details,
            )
        if self.config.budget_source == "google_sheets":
            return self._download_google_sheet(details)
        raise ConfigError(f"Unsupported budget source '{self.config.budget_source}'.")

    def download_path(self) -> Path:
        if self.config.budget_xlsx_download_path:
            return self.config.budget_xlsx_download_path
        suffix = "google.xlsx" if self.config.budget_source == "google_sheets" else "remote.xlsx"
        return self.config.db_path.with_name(f"Budget.{suffix}")

    def _download_google_sheet(self, details: dict[str, Any]) -> dict[str, Any]:
        if not self.config.google_sheets_file_id:
            raise ConfigError("FINCLAIDE_GOOGLE_SHEETS_FILE_ID is required for google_sheets source.")
        if not self.config.google_service_account_path:
            raise ConfigError("FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH is required for google_sheets source.")
        token = self._access_token_provider()()
        export_url = (
            "https://www.googleapis.com/drive/v3/files/"
            f"{quote(self.config.google_sheets_file_id, safe='')}/export"
        )
        return self._download(
            export_url,
            details=details,
            params={"mimeType": GOOGLE_SHEETS_EXPORT_MIME},
            headers={"Authorization": f"Bearer {token}"},
            error_prefix="Failed to export Google Sheets workbook",
        )

    def _download(
        self,
        url: str | None,
        *,
        details: dict[str, Any],
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        error_prefix: str = "Failed to download workbook export",
    ) -> dict[str, Any]:
        if not url:
            raise ConfigError("A workbook URL is required for remote budget sources.")
        try:
            response = self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise DataIntegrityError(f"{error_prefix}: {error}") from error

        destination = self.download_path()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        if destination.stat().st_size == 0:
            raise DataIntegrityError("Downloaded workbook export was empty.")

        details.update(
            {
                "downloaded_at": utc_now(),
                "byte_count": destination.stat().st_size,
            }
        )
        return details

    def _access_token_provider(self) -> AccessTokenProvider:
        if self.access_token_provider is not None:
            return self.access_token_provider
        return GoogleServiceAccountTokenProvider(self.config)


@dataclass
class GoogleServiceAccountTokenProvider:
    config: AppConfig

    def __call__(self) -> str:
        if not self.config.google_service_account_path:
            raise ConfigError("FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH is required for google_sheets source.")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError as error:
            raise ConfigError("google-auth support is not installed.") from error

        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.config.google_service_account_path),
                scopes=[GOOGLE_DRIVE_EXPORT_SCOPE],
            )
        except (OSError, ValueError) as error:
            raise ConfigError(
                f"Failed to load Google service account credentials: {error}"
            ) from error

        try:
            credentials.refresh(Request())
        except Exception as error:
            raise ConfigError(f"Failed to obtain a Google access token: {error}") from error
        if not credentials.token:
            raise ConfigError("Failed to obtain a Google access token from the service account.")
        return str(credentials.token)


def create_budget_workbook_source(
    config: AppConfig,
    *,
    transport: httpx.BaseTransport | None = None,
    access_token_provider: AccessTokenProvider | None = None,
) -> BudgetWorkbookSource:
    return BudgetWorkbookSource(
        config=config,
        client=httpx.Client(follow_redirects=True, transport=transport, timeout=30.0),
        access_token_provider=access_token_provider,
    )
