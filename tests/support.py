from __future__ import annotations

import json
from pathlib import Path

import httpx


FIXTURE_DIR = Path(__file__).parent / "ynab_fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def make_transport(
    *,
    categories_fixture: str = "categories.json",
    transactions_fixture: str = "transactions_initial.json",
) -> httpx.MockTransport:
    payload_map = {
        "/v1/plans/plan-123": load_fixture("plan.json"),
        "/v1/plans/plan-123/accounts": load_fixture("accounts.json"),
        "/v1/plans/plan-123/categories": load_fixture(categories_fixture),
        "/v1/plans/plan-123/transactions": load_fixture(transactions_fixture),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = payload_map.get(request.url.path)
        if payload is None:
            return httpx.Response(404, json={"error": "not_found"})
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)
