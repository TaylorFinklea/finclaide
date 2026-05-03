"""Tests for Phase 2.5f reconcile suggestions.

The suggestion engine adds a `suggested_match` field per
extra_in_ynab / missing_in_ynab item, scoring candidates with
difflib.SequenceMatcher on normalized strings (NBSP collapsed,
unicode replacement chars dropped, case-folded). Same-group matches
get a +0.1 ratio bonus."""
from __future__ import annotations

from pathlib import Path

import pytest

from finclaide.services import _normalize_for_match, _score_match
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
