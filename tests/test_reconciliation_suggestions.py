"""Tests for Phase 2.5f reconcile suggestions.

The suggestion engine adds a `suggested_match` field per
extra_in_ynab / missing_in_ynab item, scoring candidates with
difflib.SequenceMatcher on normalized strings (NBSP collapsed,
unicode replacement chars dropped, case-folded). Same-group matches
get a +0.1 ratio bonus."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from finclaide.services import _normalize_for_match, _score_match
from tests.support import load_fixture
from tests.workbook_builder import build_budget_workbook


# --- helpers --------------------------------------------------------------


def _seed(client, auth_header):
    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)


def _rename_plan_category_via_db(
    database, *, from_group: str, from_name: str, to_group: str, to_name: str
) -> None:
    """Rename a plan_categories row directly. The plan-edit API path
    treats group_name / category_name as reconcile-sensitive and forbids
    rename when targets duplicate existing rows; we use direct SQL so
    the test can set up arbitrary mismatches."""
    with database.connect() as conn:
        conn.execute(
            """
            UPDATE plan_categories SET group_name = ?, category_name = ?
            WHERE plan_id = (SELECT id FROM plans WHERE status = 'active')
              AND group_name = ? AND category_name = ?
            """,
            (to_group, to_name, from_group, from_name),
        )


def _seed_ynab_category(
    database, *, cat_id: str, group_id: str, group_name: str, name: str
) -> None:
    """Insert directly into the YNAB-mirror tables. Mirrors the shape
    used in `test_reconcile_preview_surfaces_extra_in_ynab` upstream."""
    with database.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO category_groups(
                id, plan_id, name, hidden, deleted, raw_json, updated_at
            ) VALUES (?, 'plan-123', ?, 0, 0, '{}', '2026-03-15T12:00:00+00:00')
            """,
            (group_id, group_name),
        )
        conn.execute(
            """
            INSERT INTO categories(
                id, plan_id, group_id, group_name, name,
                hidden, deleted, balance_milliunits, raw_json, updated_at
            ) VALUES (?, 'plan-123', ?, ?, ?, 0, 0, 0, '{}', '2026-03-15T12:00:00+00:00')
            """,
            (cat_id, group_id, group_name, name),
        )


class StatefulYnabTransport(httpx.MockTransport):
    def __init__(self) -> None:
        self.plan = load_fixture("plan.json")
        self.accounts = load_fixture("accounts.json")
        self.transactions = load_fixture("transactions_initial.json")
        self.categories = deepcopy(load_fixture("categories.json"))
        self.requests: list[httpx.Request] = []
        super().__init__(self._handler)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/plans/plan-123":
            return httpx.Response(200, json=self.plan)
        if path == "/v1/plans/plan-123/accounts":
            return httpx.Response(200, json=self.accounts)
        if path == "/v1/plans/plan-123/categories" and request.method == "GET":
            return httpx.Response(200, json=self.categories)
        if path == "/v1/plans/plan-123/transactions":
            return httpx.Response(200, json=self.transactions)
        if path == "/v1/plans/plan-123/categories" and request.method == "POST":
            body = request.read()
            payload = json.loads(body)
            category = payload["category"]
            group = self._group_by_id(category["category_group_id"])
            created = {
                "id": f"cat-created-{len(group['categories']) + 1}",
                "name": category["name"],
                "hidden": False,
                "deleted": False,
                "balance": 0,
            }
            group["categories"].append(created)
            return httpx.Response(201, json={"data": {"category": created}})
        if path == "/v1/plans/plan-123/category_groups" and request.method == "POST":
            body = request.read()
            payload = json.loads(body)
            created = {
                "id": f"grp-created-{len(self.categories['data']['category_groups']) + 1}",
                "name": payload["category_group"]["name"],
                "hidden": False,
                "deleted": False,
                "categories": [],
            }
            self.categories["data"]["category_groups"].append(created)
            return httpx.Response(201, json={"data": {"category_group": created}})
        if path.startswith("/v1/plans/plan-123/categories/") and request.method == "PATCH":
            category_id = path.rsplit("/", 1)[1]
            body = request.read()
            payload = json.loads(body)
            updates = payload["category"]
            category = self._category_by_id(category_id)
            target_group = self._group_by_id(updates["category_group_id"])
            current_group = self._group_for_category(category_id)
            if current_group["id"] != target_group["id"]:
                current_group["categories"].remove(category)
                target_group["categories"].append(category)
            category["name"] = updates["name"]
            return httpx.Response(200, json={"data": {"category": category}})
        return httpx.Response(404, json={"error": "not_found", "path": path})

    def _group_by_id(self, group_id: str) -> dict:
        for group in self.categories["data"]["category_groups"]:
            if group["id"] == group_id:
                return group
        raise AssertionError(f"group not found: {group_id}")

    def _category_by_id(self, category_id: str) -> dict:
        for group in self.categories["data"]["category_groups"]:
            for category in group["categories"]:
                if category["id"] == category_id:
                    return category
        raise AssertionError(f"category not found: {category_id}")

    def _group_for_category(self, category_id: str) -> dict:
        for group in self.categories["data"]["category_groups"]:
            for category in group["categories"]:
                if category["id"] == category_id:
                    return group
        raise AssertionError(f"category group not found: {category_id}")


# --- normalization + scoring (pure unit) ----------------------------------


def test_normalize_collapses_non_breaking_space_and_drops_replacement_char():
    assert _normalize_for_match("Apple\xa0Card") == "apple card"
    assert _normalize_for_match("Wells Fargo Visa�� Card") == "wells fargo visa card"


def test_score_match_same_group_gets_bonus():
    same = _score_match(
        plan_group="Yearly",
        plan_name="Wk Trip ($2k-$3k)",
        ynab_group="Yearly",
        ynab_name="Week Trip ($2k-$3k)",
    )
    cross = _score_match(
        plan_group="Bills",
        plan_name="Wk Trip ($2k-$3k)",
        ynab_group="Yearly",
        ynab_name="Week Trip ($2k-$3k)",
    )
    assert same > cross
    assert (same - cross) == pytest.approx(0.10, abs=1e-9)


# --- preview suggestions (integration via app_factory) --------------------


def test_no_suggestions_when_already_in_sync(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    _seed(client, auth_header)

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    # Existing fixture pair has no drift; missing_in_ynab is empty.
    assert payload["counts"]["missing_in_ynab"] == 0


def test_suggests_high_confidence_rename_in_same_group(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, auth_header)

    # Plan keeps "Vacation" (Yearly group). Rename it to "Vaction" so
    # YNAB's correct spelling shows as extra and the plan side as missing.
    _rename_plan_category_via_db(
        services.database,
        from_group="Yearly",
        from_name="Vacation",
        to_group="Yearly",
        to_name="Vaction",
    )

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    extras = {item["category_name"]: item for item in payload["extra_in_ynab"]}
    assert "Vacation" in extras
    suggestion = extras["Vacation"]["suggested_match"]
    assert suggestion is not None
    assert suggestion["category_name"] == "Vaction"
    assert suggestion["group_name"] == "Yearly"
    assert suggestion["confidence"] >= 0.9
    # plan_category_id is set on extra_in_ynab suggestions so the
    # frontend can PATCH directly.
    assert isinstance(suggestion["plan_category_id"], int)


def test_suggested_match_handles_non_breaking_space(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, auth_header)

    # Plan keeps a clean name; YNAB picks up an NBSP variant.
    _rename_plan_category_via_db(
        services.database,
        from_group="Savings",
        from_name="Investments",
        to_group="Savings",
        to_name="Brokerage",
    )
    _seed_ynab_category(
        services.database,
        cat_id="cat-nbsp",
        group_id="grp-savings-extra",
        group_name="Savings",
        name="Brokerage\xa0",
    )

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    extras = {item["category_name"]: item for item in payload["extra_in_ynab"]}
    target = "Brokerage\xa0"
    assert target in extras
    suggestion = extras[target]["suggested_match"]
    assert suggestion is not None
    assert suggestion["category_name"] == "Brokerage"


def test_suggested_match_drops_replacement_chars(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, auth_header)

    _rename_plan_category_via_db(
        services.database,
        from_group="Savings",
        from_name="Investments",
        to_group="Savings",
        to_name="Brokerage Account",
    )
    _seed_ynab_category(
        services.database,
        cat_id="cat-replacement",
        group_id="grp-savings-extra",
        group_name="Savings",
        name="Brokerage�� Account",
    )

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    extras = {item["category_name"]: item for item in payload["extra_in_ynab"]}
    target = "Brokerage�� Account"
    assert target in extras
    suggestion = extras[target]["suggested_match"]
    assert suggestion is not None
    assert suggestion["category_name"] == "Brokerage Account"


def test_low_confidence_returns_no_suggestion(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, auth_header)

    # Rename plan's "Investments" to something completely unrelated.
    # YNAB still has Investments → extra_in_ynab. The plan side
    # ("Aardvark Fund") shouldn't match anything via similarity.
    _rename_plan_category_via_db(
        services.database,
        from_group="Savings",
        from_name="Investments",
        to_group="Savings",
        to_name="Aardvark Fund",
    )

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    extras = {item["category_name"]: item for item in payload["extra_in_ynab"]}
    assert "Investments" in extras
    # Low similarity → no suggested match.
    assert extras["Investments"]["suggested_match"] is None


def test_missing_in_ynab_carries_suggestion_pointing_at_ynab_name(
    app_factory, auth_header, tmp_path: Path,
):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, auth_header)

    _rename_plan_category_via_db(
        services.database,
        from_group="Yearly",
        from_name="Vacation",
        to_group="Yearly",
        to_name="Vaction",
    )

    payload = client.get("/api/reconcile/preview", headers=auth_header).get_json()
    missing = {item["category_name"]: item for item in payload["missing_in_ynab"]}
    assert "Vaction" in missing
    suggestion = missing["Vaction"]["suggested_match"]
    assert suggestion is not None
    # Suggestions on missing_in_ynab point AT the YNAB-correct name,
    # not at a plan id (the row's own id is implicit).
    assert suggestion["category_name"] == "Vacation"
    assert suggestion["plan_category_id"] is None


def test_apply_plan_to_ynab_renames_suggested_ynab_category(
    app_factory, ui_headers, tmp_path: Path,
):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    transport = StatefulYnabTransport()
    app = app_factory(workbook_path=workbook, ynab_transport=transport)
    client = app.test_client()
    services = app.extensions["finclaide"]
    _seed(client, {"Authorization": "Bearer test-token"})

    _rename_plan_category_via_db(
        services.database,
        from_group="Yearly",
        from_name="Vacation",
        to_group="Yearly",
        to_name="Vaction",
    )

    response = client.post(
        "/ui-api/reconcile/apply-plan-to-ynab",
        headers=ui_headers,
        json={
            "operation": "rename_category",
            "source": {"group_name": "Yearly", "category_name": "Vacation"},
            "target": {"group_name": "Yearly", "category_name": "Vaction"},
        },
    )

    payload = response.get_json()
    patch_request = next(
        request
        for request in transport.requests
        if request.method == "PATCH"
        and request.url.path == "/v1/plans/plan-123/categories/cat-vacation"
    )
    assert response.status_code == 200
    assert payload["action"]["kind"] == "renamed_category"
    assert payload["reconcile"]["mismatch_count"] == 0
    assert json.loads(patch_request.content)["category"] == {
        "name": "Vaction",
        "category_group_id": "grp-yearly",
    }


def test_apply_plan_to_ynab_creates_missing_ynab_category(
    app_factory, ui_headers, tmp_path: Path,
):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    transport = StatefulYnabTransport()
    app = app_factory(workbook_path=workbook, ynab_transport=transport)
    client = app.test_client()
    _seed(client, {"Authorization": "Bearer test-token"})

    active_plan = client.get("/ui-api/plan/active").get_json()
    client.post(
        "/ui-api/plan/categories",
        headers=ui_headers,
        json={
            "plan_id": active_plan["plan"]["id"],
            "group_name": "Expenses",
            "category_name": "Homeschool",
            "block": "monthly",
            "kind": "outflow",
            "planned_milliunits": 0,
            "annual_target_milliunits": 0,
            "due_month": None,
            "notes": None,
        },
    )

    response = client.post(
        "/ui-api/reconcile/apply-plan-to-ynab",
        headers=ui_headers,
        json={
            "operation": "create_category",
            "target": {"group_name": "Expenses", "category_name": "Homeschool"},
        },
    )

    payload = response.get_json()
    post_request = next(
        request
        for request in transport.requests
        if request.method == "POST"
        and request.url.path == "/v1/plans/plan-123/categories"
    )
    assert response.status_code == 200
    assert payload["action"]["kind"] == "created_category"
    assert payload["reconcile"]["mismatch_count"] == 0
    assert json.loads(post_request.content)["category"] == {
        "name": "Homeschool",
        "category_group_id": "grp-expenses",
    }
