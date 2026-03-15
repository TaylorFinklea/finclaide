from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from finclaide.mcp_config import MCPConfig


class FinclaideApiError(Exception):
    def __init__(self, *, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Finclaide API returned {status_code}: {payload}")


class FinclaideUnavailableError(Exception):
    pass


@dataclass
class FinclaideApiClient:
    config: MCPConfig
    transport: httpx.BaseTransport | None = None

    def __post_init__(self) -> None:
        headers = {}
        if self.config.api_token:
            headers["Authorization"] = f"Bearer {self.config.api_token}"
        self._client = httpx.Client(
            base_url=self.config.api_base_url,
            headers=headers,
            timeout=30.0,
            transport=self.transport,
        )

    def close(self) -> None:
        self._client.close()

    def check_health(self) -> dict[str, Any]:
        try:
            response = self._client.get(self.config.health_url)
        except httpx.HTTPError as error:
            raise FinclaideUnavailableError(f"Could not reach Finclaide health check: {error}") from error
        if response.status_code != 200:
            raise FinclaideUnavailableError(
                f"Finclaide health check failed with {response.status_code}: {self._response_payload(response)}"
            )
        payload = response.json()
        if payload.get("status") != "ok":
            raise FinclaideUnavailableError(f"Finclaide health check returned unexpected payload: {payload}")
        return payload

    def get_status(self) -> dict[str, Any]:
        return self._request_json("GET", "/status")

    def import_budget(self) -> dict[str, Any]:
        return self._request_json("POST", "/budget/import")

    def sync_ynab(self) -> dict[str, Any]:
        return self._request_json("POST", "/ynab/sync")

    def reconcile(self) -> dict[str, Any]:
        return self._request_json("POST", "/reconcile")

    def get_summary(self, month: str | None = None) -> dict[str, Any]:
        params = {"month": month} if month else None
        return self._request_json("GET", "/reports/summary", params=params)

    def get_transactions(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
        group: str | None = None,
        category: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params = {
            key: value
            for key, value in {
                "since": since,
                "until": until,
                "group": group,
                "category": category,
                "limit": limit,
            }.items()
            if value is not None
        }
        return self._request_json("GET", "/transactions", params=params or None)

    def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise FinclaideUnavailableError(f"Could not reach Finclaide API: {error}") from error
        if response.status_code >= 400:
            raise FinclaideApiError(status_code=response.status_code, payload=self._response_payload(response))
        return response.json()

    def _response_payload(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"error": response.text}
