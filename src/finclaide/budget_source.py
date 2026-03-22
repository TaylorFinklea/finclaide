from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from finclaide.config import AppConfig
from finclaide.errors import DataIntegrityError
from finclaide.database import utc_now


@dataclass
class BudgetWorkbookSource:
    config: AppConfig
    client: httpx.Client

    def describe(self) -> dict[str, Any]:
        if self.config.budget_xlsx_url:
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
        if self.config.budget_xlsx_url:
            return self.download_path()
        return self.config.budget_xlsx

    def prepare(self) -> dict[str, Any]:
        details = self.describe()
        if not self.config.budget_xlsx_url:
            return details

        response = None
        try:
            response = self.client.get(self.config.budget_xlsx_url)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise DataIntegrityError(f"Failed to download workbook export: {error}") from error

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

    def download_path(self) -> Path:
        if self.config.budget_xlsx_download_path:
            return self.config.budget_xlsx_download_path
        return self.config.db_path.with_name("Budget.remote.xlsx")


def create_budget_workbook_source(
    config: AppConfig,
    *,
    transport: httpx.BaseTransport | None = None,
) -> BudgetWorkbookSource:
    return BudgetWorkbookSource(
        config=config,
        client=httpx.Client(follow_redirects=True, transport=transport, timeout=30.0),
    )
