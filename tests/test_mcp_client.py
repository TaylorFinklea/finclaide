from __future__ import annotations

import httpx
import pytest

from finclaide.mcp_client import FinclaideApiClient, FinclaideApiError, FinclaideUnavailableError
from finclaide.mcp_config import MCPConfig


def test_mcp_client_sends_bearer_token():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"plan_id": "plan-123"})

    client = FinclaideApiClient(
        MCPConfig(
            api_base_url="http://finclaide.test/api",
            api_token="secret-token",
            health_url="http://finclaide.test/healthz",
        ),
        transport=httpx.MockTransport(handler),
    )

    assert client.get_status() == {"plan_id": "plan-123"}
    assert captured["authorization"] == "Bearer secret-token"


@pytest.mark.parametrize("status_code", [400, 401, 409, 500])
def test_mcp_client_raises_api_errors(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": f"status-{status_code}"})

    client = FinclaideApiClient(
        MCPConfig(
            api_base_url="http://finclaide.test/api",
            api_token="secret-token",
            health_url="http://finclaide.test/healthz",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(FinclaideApiError) as excinfo:
        client.get_status()

    assert excinfo.value.status_code == status_code
    assert excinfo.value.payload == {"error": f"status-{status_code}"}


def test_mcp_client_reports_health_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    client = FinclaideApiClient(
        MCPConfig(
            api_base_url="http://finclaide.test/api",
            api_token="secret-token",
            health_url="http://finclaide.test/healthz",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(FinclaideUnavailableError, match="health check failed"):
        client.check_health()


def test_mcp_client_handles_non_json_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = FinclaideApiClient(
        MCPConfig(
            api_base_url="http://finclaide.test/api",
            api_token="secret-token",
            health_url="http://finclaide.test/healthz",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(FinclaideApiError) as excinfo:
        client.get_status()

    assert excinfo.value.payload == {"error": "boom"}
