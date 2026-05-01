from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from finclaide.config import AppConfig
from finclaide.database import utc_now
from finclaide.errors import ConfigError, DataIntegrityError
from finclaide.plan_exporter import build_plan_cell_grid
from finclaide.plan_service import PlanService

GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

# Google's tab title cap.
_MAX_TAB_NAME_LENGTH = 100
_TAB_NAME_TEMPLATE = "{base} — published {stamp}"

# Cells in a column-letter+row-number form. We accept the cells dict from
# `build_plan_cell_grid` and translate it directly into Sheets API
# `userEnteredValue` payloads.
AccessTokenProvider = Callable[[], str]


@dataclass
class PublishResult:
    spreadsheet_id: str
    tab_name: str
    tab_id: int
    tab_url: str
    file_size_bytes: int  # approximated by JSON payload length
    row_count: int


class SheetsPublisher:
    """Publishes the active plan as a new tab in the configured Google
    Sheets workbook. The canonical source tab is never touched — the
    importer keeps reading whatever `config.budget_sheet_name` points at."""

    def __init__(
        self,
        *,
        plan_service: PlanService,
        config: AppConfig,
        client: httpx.Client,
        access_token_provider: AccessTokenProvider | None = None,
    ):
        self._plan_service = plan_service
        self._config = config
        self._client = client
        self._access_token_provider = access_token_provider

    def publish(self, *, now: str | None = None) -> PublishResult:
        if self._config.budget_source != "google_sheets":
            raise ConfigError(
                "Publish to Sheets requires FINCLAIDE_BUDGET_SOURCE=google_sheets "
                "and FINCLAIDE_GOOGLE_SHEETS_FILE_ID configured."
            )
        if not self._config.google_sheets_file_id:
            raise ConfigError(
                "FINCLAIDE_GOOGLE_SHEETS_FILE_ID is required to publish to Sheets."
            )

        plan = self._plan_service.get_active_plan()
        grid = build_plan_cell_grid(plan)
        timestamp = now or utc_now()

        token = self._token_provider()()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        spreadsheet_id = self._config.google_sheets_file_id
        encoded_id = quote(spreadsheet_id, safe="")

        base_name = self._config.budget_sheet_name
        target_name, tab_id = self._add_tab(
            encoded_id=encoded_id,
            headers=headers,
            base_name=base_name,
            timestamp=timestamp,
        )
        payload_byte_count = self._write_cells(
            encoded_id=encoded_id,
            headers=headers,
            target_name=target_name,
            cells=grid.cells,
        )
        return PublishResult(
            spreadsheet_id=spreadsheet_id,
            tab_name=target_name,
            tab_id=tab_id,
            tab_url=(
                f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
                f"/edit#gid={tab_id}"
            ),
            file_size_bytes=payload_byte_count,
            row_count=grid.row_count,
        )

    # --- internal helpers --------------------------------------------------

    def _token_provider(self) -> AccessTokenProvider:
        if self._access_token_provider is not None:
            return self._access_token_provider
        return _SheetsServiceAccountTokenProvider(self._config)

    def _add_tab(
        self,
        *,
        encoded_id: str,
        headers: dict[str, str],
        base_name: str,
        timestamp: str,
    ) -> tuple[str, int]:
        """Adds a new sheet/tab; on title collision (same minute, same base),
        appends `(2)`, `(3)`, … until a successful response. Returns the
        chosen title and the new sheet's `sheetId`."""
        candidate = _build_tab_name(base_name, timestamp)
        for attempt in range(1, 11):
            request = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {"title": candidate},
                        }
                    }
                ]
            }
            url = f"{SHEETS_API_BASE}/{encoded_id}:batchUpdate"
            try:
                response = self._client.post(url, json=request, headers=headers)
            except httpx.HTTPError as error:
                raise DataIntegrityError(
                    f"Failed to call Sheets batchUpdate: {error}"
                ) from error
            if response.status_code == 200:
                payload = _safe_json(response)
                replies = payload.get("replies") or []
                if not replies:
                    raise DataIntegrityError(
                        "Sheets batchUpdate(addSheet) returned no replies."
                    )
                props = (replies[0].get("addSheet") or {}).get("properties") or {}
                tab_id = props.get("sheetId")
                if tab_id is None:
                    raise DataIntegrityError(
                        "Sheets batchUpdate(addSheet) reply missing sheetId."
                    )
                return candidate, int(tab_id)
            if response.status_code == 400 and _is_duplicate_title_error(response):
                candidate = _bump_collision_suffix(candidate, attempt + 1)
                continue
            raise DataIntegrityError(
                "Sheets batchUpdate(addSheet) failed with "
                f"status {response.status_code}: {response.text[:300]}"
            )
        raise DataIntegrityError(
            "Could not find a free tab name after 10 collision retries."
        )

    def _write_cells(
        self,
        *,
        encoded_id: str,
        headers: dict[str, str],
        target_name: str,
        cells: dict[str, str | float],
    ) -> int:
        """Writes all populated cells via `values:batchUpdate`. Uses
        `USER_ENTERED` so formulas (`=SUM(...)`) are honored and Sheets
        recomputes the cached value server-side. We don't send empty
        cells; group-row amount columns are simply absent from the
        request, matching the importer's expectations."""
        # Group by column-major chunks that share a column letter; the
        # API needs a separate value range per contiguous range. The
        # simplest correct option is one value range per cell; for a
        # ~80-cell payload that's fine.
        data_payload = []
        for cell_ref, value in cells.items():
            data_payload.append(
                {
                    "range": f"'{target_name}'!{cell_ref}",
                    "majorDimension": "ROWS",
                    "values": [[value]],
                }
            )
        request = {"valueInputOption": "USER_ENTERED", "data": data_payload}
        url = f"{SHEETS_API_BASE}/{encoded_id}/values:batchUpdate"
        try:
            response = self._client.post(url, json=request, headers=headers)
        except httpx.HTTPError as error:
            raise DataIntegrityError(
                f"Failed to call Sheets values:batchUpdate: {error}"
            ) from error
        if response.status_code != 200:
            raise DataIntegrityError(
                "Sheets values:batchUpdate failed with "
                f"status {response.status_code}: {response.text[:300]}"
            )
        return len(response.request.content) if response.request.content else 0


def _build_tab_name(base: str, timestamp: str) -> str:
    # Trim e.g. "2026-04-30T19:42:00+00:00" → "2026-04-30 1942"
    stamp_match = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", timestamp)
    if stamp_match:
        date_part, hour, minute = stamp_match.groups()
        stamp = f"{date_part} {hour}{minute}"
    else:
        stamp = timestamp[:16]
    full = _TAB_NAME_TEMPLATE.format(base=base, stamp=stamp)
    return full[:_MAX_TAB_NAME_LENGTH]


def _bump_collision_suffix(candidate: str, attempt: int) -> str:
    base = re.sub(r" \(\d+\)$", "", candidate)
    bumped = f"{base} ({attempt})"
    return bumped[:_MAX_TAB_NAME_LENGTH]


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as error:
        raise DataIntegrityError("Sheets API returned non-JSON response.") from error
    if not isinstance(body, dict):
        raise DataIntegrityError("Sheets API response was not a JSON object.")
    return body


def _is_duplicate_title_error(response: httpx.Response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return False
    message = (error.get("message") or "").lower()
    return "already exists" in message or "duplicate" in message


@dataclass
class _SheetsServiceAccountTokenProvider:
    """Mirrors `GoogleServiceAccountTokenProvider` from `budget_source.py`,
    but requests the Sheets scope (write) instead of `drive.readonly`."""

    config: AppConfig

    def __call__(self) -> str:
        if not self.config.google_service_account_path:
            raise ConfigError(
                "FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH is required to publish to Sheets."
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError as error:
            raise ConfigError("google-auth support is not installed.") from error

        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.config.google_service_account_path),
                scopes=[GOOGLE_SHEETS_SCOPE],
            )
        except (OSError, ValueError) as error:
            raise ConfigError(
                f"Failed to load Google service account credentials: {error}"
            ) from error
        try:
            credentials.refresh(Request())
        except Exception as error:
            raise ConfigError(
                f"Failed to obtain a Google access token: {error}"
            ) from error
        if not credentials.token:
            raise ConfigError(
                "Failed to obtain a Google access token from the service account."
            )
        return str(credentials.token)


def create_sheets_publisher(
    *,
    plan_service: PlanService,
    config: AppConfig,
    transport: httpx.BaseTransport | None = None,
    access_token_provider: AccessTokenProvider | None = None,
) -> SheetsPublisher:
    return SheetsPublisher(
        plan_service=plan_service,
        config=config,
        client=httpx.Client(follow_redirects=True, transport=transport, timeout=30.0),
        access_token_provider=access_token_provider,
    )
