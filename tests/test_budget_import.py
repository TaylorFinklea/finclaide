from __future__ import annotations

from pathlib import Path

import pytest

from finclaide.budget_sheet import BudgetImporter
from finclaide.database import Database
from finclaide.errors import DataIntegrityError
from tests.workbook_builder import build_budget_workbook


def test_import_budget_success(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    database = Database(tmp_path / "test.db")
    database.initialize()

    summary = BudgetImporter(database).import_budget(workbook, "2026 Budget")

    assert summary["row_count"] == 11
    assert summary["plan_year"] == 2026
    with database.connect() as connection:
        planned_rows = connection.execute(
            "SELECT group_name, category_name, block, planned_milliunits FROM v_latest_planned_categories ORDER BY id"
        ).fetchall()
    assert planned_rows[0]["group_name"] == "Bills"
    assert planned_rows[0]["category_name"] == "Rent"
    assert planned_rows[-1]["group_name"] == "Savings"
    assert planned_rows[-1]["planned_milliunits"] == 75000


def test_import_budget_rejects_duplicate_categories(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", duplicate_category=True)
    database = Database(tmp_path / "test.db")
    database.initialize()

    with pytest.raises(DataIntegrityError, match="Duplicate planned categories"):
        BudgetImporter(database).import_budget(workbook, "2026 Budget")


def test_import_budget_requires_cached_formula_values(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", missing_cached_formula=True)
    database = Database(tmp_path / "test.db")
    database.initialize()

    with pytest.raises(DataIntegrityError, match="Missing cached formula result in G53"):
        BudgetImporter(database).import_budget(workbook, "2026 Budget")


def test_import_budget_requires_expected_sheet_name(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", wrong_sheet_name=True)
    database = Database(tmp_path / "test.db")
    database.initialize()

    with pytest.raises(DataIntegrityError, match="Required sheet '2026 Budget'"):
        BudgetImporter(database).import_budget(workbook, "2026 Budget")


def test_import_budget_requires_expected_layout(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", invalid_layout=True)
    database = Database(tmp_path / "test.db")
    database.initialize()

    with pytest.raises(DataIntegrityError, match="Expected 'Stipends' header"):
        BudgetImporter(database).import_budget(workbook, "2026 Budget")
