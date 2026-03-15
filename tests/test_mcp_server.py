from __future__ import annotations

import os
import threading
from pathlib import Path

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.fastmcp.exceptions import ToolError
from werkzeug.serving import make_server

from finclaide.mcp_client import FinclaideApiClient
from finclaide.mcp_config import MCPConfig
from finclaide.mcp_server import create_mcp_server
from tests.workbook_builder import build_budget_workbook


@pytest.mark.anyio
async def test_mcp_server_lists_tools_resources_and_prompts():
    config = MCPConfig(
        api_base_url="http://finclaide.test/api",
        api_token="token",
        health_url="http://finclaide.test/healthz",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"plan_id": "plan-123"})
        if request.url.path == "/api/reports/summary":
            month = request.url.params.get("month", "2026-03")
            return httpx.Response(200, json={"month": month, "mismatches": [], "groups": []})
        if request.url.path == "/api/transactions":
            return httpx.Response(200, json={"transactions": []})
        raise AssertionError(f"Unexpected path {request.url.path}")

    api_client = FinclaideApiClient(config, transport=httpx.MockTransport(handler))
    server = create_mcp_server(config, api_client=api_client)

    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert {
        "get_status",
        "get_summary",
        "list_transactions",
        "import_budget",
        "sync_ynab",
        "reconcile",
        "refresh_all",
        "api_get_status",
        "api_post_budget_import",
        "api_post_ynab_sync",
        "api_post_reconcile",
        "api_get_reports_summary",
        "api_get_transactions",
    }.issubset(tool_names)

    resources = await server.list_resources()
    resource_uris = {str(resource.uri) for resource in resources}
    assert "finclaide://status" in resource_uris
    assert "finclaide://summary/current" in resource_uris
    assert "finclaide://reconciliation/latest" in resource_uris
    assert "finclaide://transactions/recent" in resource_uris

    templates = await server.list_resource_templates()
    template_uris = {template.uriTemplate for template in templates}
    assert "finclaide://summary/{month}" in template_uris
    assert "finclaide://transactions/{since}/{until}/{group}/{category}/{limit}" in template_uris

    prompts = await server.list_prompts()
    prompt_names = {prompt.name for prompt in prompts}
    assert {"monthly_review", "investigate_mismatches", "spending_check"} == prompt_names


@pytest.mark.anyio
async def test_mcp_server_reads_resources_and_prompts():
    config = MCPConfig(
        api_base_url="http://finclaide.test/api",
        api_token="token",
        health_url="http://finclaide.test/healthz",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/status":
            return httpx.Response(
                200,
                json={
                    "plan_id": "plan-123",
                    "last_reconcile_at": "2026-03-15T12:00:24.000000+00:00",
                    "last_reconcile_status": "success",
                },
            )
        if request.url.path == "/api/reports/summary":
            return httpx.Response(
                200,
                json={"month": request.url.params.get("month", "2026-03"), "mismatches": [], "groups": []},
            )
        if request.url.path == "/api/transactions":
            return httpx.Response(200, json={"transactions": [{"date": "2026-03-15"}]})
        raise AssertionError(f"Unexpected path {request.url.path}")

    api_client = FinclaideApiClient(config, transport=httpx.MockTransport(handler))
    server = create_mcp_server(config, api_client=api_client)

    status_contents = await server.read_resource("finclaide://status")
    assert '"plan_id": "plan-123"' in status_contents[0].content

    summary_contents = await server.read_resource("finclaide://summary/2026-03")
    assert '"month": "2026-03"' in summary_contents[0].content

    recent_contents = await server.read_resource("finclaide://transactions/recent")
    assert '"date": "2026-03-15"' in recent_contents[0].content

    prompt = await server.get_prompt("monthly_review", {"month": "2026-03"})
    assert "2026-03" in prompt.messages[0].content.text


@pytest.mark.anyio
async def test_mcp_server_tool_outputs_and_refresh_order():
    call_order: list[str] = []
    config = MCPConfig(
        api_base_url="http://finclaide.test/api",
        api_token="token",
        health_url="http://finclaide.test/healthz",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/budget/import":
            call_order.append("import")
            return httpx.Response(200, json={"row_count": 75})
        if request.url.path == "/api/ynab/sync":
            call_order.append("sync")
            return httpx.Response(200, json={"transaction_count": 11})
        if request.url.path == "/api/reconcile":
            call_order.append("reconcile")
            return httpx.Response(200, json={"mismatch_count": 0})
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"last_reconcile_status": "success"})
        if request.url.path == "/api/reports/summary":
            return httpx.Response(200, json={"month": request.url.params.get("month", "2026-03"), "groups": []})
        if request.url.path == "/api/transactions":
            return httpx.Response(200, json={"transactions": []})
        raise AssertionError(f"Unexpected path {request.url.path}")

    api_client = FinclaideApiClient(config, transport=httpx.MockTransport(handler))
    server = create_mcp_server(config, api_client=api_client)

    _, summary = await server.call_tool("get_summary", {"month": "2026-03"})
    assert summary["month"] == "2026-03"

    _, refresh = await server.call_tool("refresh_all", {"month": "2026-03"})
    assert call_order == ["import", "sync", "reconcile"]
    assert refresh["import_result"]["row_count"] == 75
    assert refresh["sync_result"]["transaction_count"] == 11
    assert refresh["reconcile_result"]["mismatch_count"] == 0
    assert refresh["summary"]["month"] == "2026-03"


@pytest.mark.anyio
async def test_mcp_server_refresh_surfaces_reconcile_errors():
    config = MCPConfig(
        api_base_url="http://finclaide.test/api",
        api_token="token",
        health_url="http://finclaide.test/healthz",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/budget/import":
            return httpx.Response(200, json={"row_count": 75})
        if request.url.path == "/api/ynab/sync":
            return httpx.Response(200, json={"transaction_count": 11})
        if request.url.path == "/api/reconcile":
            return httpx.Response(400, json={"error": "Reconciliation failed with 2 mismatches."})
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"last_reconcile_status": "failed"})
        if request.url.path == "/api/reports/summary":
            return httpx.Response(200, json={"month": "2026-03", "mismatches": [{"category_name": "Missing"}]})
        raise AssertionError(f"Unexpected path {request.url.path}")

    api_client = FinclaideApiClient(config, transport=httpx.MockTransport(handler))
    server = create_mcp_server(config, api_client=api_client)

    _, payload = await server.call_tool("refresh_all", {"month": "2026-03"})
    assert payload["reconcile_result"] is None
    assert payload["reconcile_error"]["status_code"] == 400
    assert payload["reconcile_error"]["payload"] == {"error": "Reconciliation failed with 2 mismatches."}


@pytest.mark.anyio
async def test_mcp_server_propagates_busy_lock_errors(app_factory, tmp_path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    transport = httpx.WSGITransport(app=app)
    config = MCPConfig(
        api_base_url="http://finclaide.test/api",
        api_token="test-token",
        health_url="http://finclaide.test/healthz",
    )
    api_client = FinclaideApiClient(config, transport=transport)
    server = create_mcp_server(config, api_client=api_client)
    services = app.extensions["finclaide"]

    with services.operation_lock.guard("hold-open"):
        with pytest.raises(ToolError) as excinfo:
            await server.call_tool("sync_ynab", {})

    assert "409" in str(excinfo.value)


@pytest.mark.anyio
async def test_finclaide_mcp_stdio_launch(app_factory, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)

    http_server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()

    try:
        port = http_server.server_port
        env = {
            **os.environ,
            "PYTHONPATH": str(repo_root / "src"),
            "FINCLAIDE_API_BASE_URL": f"http://127.0.0.1:{port}/api",
            "FINCLAIDE_API_TOKEN": "test-token",
            "FINCLAIDE_HEALTH_URL": f"http://127.0.0.1:{port}/healthz",
        }
        params = StdioServerParameters(
            command=str(repo_root / ".venv" / "bin" / "python"),
            args=["-m", "finclaide.mcp_server"],
            cwd=repo_root,
            env=env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert any(tool.name == "get_summary" for tool in tools.tools)
                result = await session.call_tool("get_summary", {"month": "2026-03"})
                assert result.structuredContent["month"] == "2026-03"
    finally:
        http_server.shutdown()
        thread.join(timeout=5)
