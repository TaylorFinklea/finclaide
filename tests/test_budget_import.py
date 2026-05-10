from __future__ import annotations

from pathlib import Path

import pytest

from finclaide.budget_sheet import BudgetImporter, PlannedCategoryRow
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


def test_import_budget_supports_current_layout(tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", layout="current")
    database = Database(tmp_path / "test.db")
    database.initialize()

    summary = BudgetImporter(database).import_budget(workbook, "2026 Budget")

    # 13 outflow rows + 2 inflow rows (Salary, Bonus) = 15. Inflow rows are
    # captured under the 'Monthly Income' / 'Yearly Income' groups so the
    # planning page cascade has an income pool to subtract from.
    assert summary["row_count"] == 15
    with database.connect() as connection:
        planned_rows = connection.execute(
            """
            SELECT group_name, category_name, block, due_month, planned_milliunits
            FROM v_latest_planned_categories
            ORDER BY id
            """
        ).fetchall()

    assert any(
        row["group_name"] == "Fun"
        and row["category_name"] == "Soda"
        and row["block"] == "stipends"
        for row in planned_rows
    )
    assert any(
        row["group_name"] == "Yearly"
        and row["category_name"] == "Feb - YNAB"
        and row["due_month"] == 2
        for row in planned_rows
    )


def test_import_tags_income_groups_as_inflow(tmp_path: Path):
    """Importer should classify rows in 'Monthly Income' / 'Yearly Income'
    groups as kind='inflow' so the planning page cascade has an income pool
    without manual data entry."""
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx", layout="current")
    database = Database(tmp_path / "test.db")
    database.initialize()
    BudgetImporter(database).import_budget(workbook, "2026 Budget")

    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT group_name, category_name, kind
            FROM plan_categories
            ORDER BY id
            """
        ).fetchall()
    by_name = {row["category_name"]: dict(row) for row in rows}
    assert by_name["Salary"]["kind"] == "inflow"
    assert by_name["Bonus"]["kind"] == "inflow"
    assert by_name["Rent"]["kind"] == "outflow"
    assert by_name["S Stipend"]["kind"] == "outflow"


def test_extract_sum_range_parses_basic_formula():
    """Helper used by the validator to identify which rows are inside the
    cached SUM. Plain `=SUM(F10:F61)` should yield the column/row tuple."""
    parsed = BudgetImporter._extract_sum_range("=SUM(F10:F61)")
    assert parsed == ("F", 10, "F", 61)


def test_extract_sum_range_handles_whitespace_and_lowercase():
    parsed = BudgetImporter._extract_sum_range("= sum( G8 : G51 )")
    assert parsed == ("G", 8, "G", 51)


def test_extract_sum_range_returns_none_for_non_sum():
    assert BudgetImporter._extract_sum_range("=AVERAGE(B5:B10)") is None
    assert BudgetImporter._extract_sum_range(None) is None


def test_rows_outside_range_flags_offenders():
    """A parsed row whose source_cell row number falls outside the cached
    SUM range should be returned so the validator can name it in the error."""
    rows = [
        PlannedCategoryRow(
            group_name="Yearly Income",
            category_name="Feb - Valentines Day",
            block="annual",
            source_cell="F9",
            planned_milliunits=33333,
            annual_target_milliunits=400000,
            due_month=2,
            formula_text=None,
        ),
        PlannedCategoryRow(
            group_name="Yearly",
            category_name="Mar - Adobe Lightroom",
            block="annual",
            source_cell="F17",
            planned_milliunits=20000,
            annual_target_milliunits=240000,
            due_month=3,
            formula_text=None,
        ),
    ]
    offenders = BudgetImporter._rows_outside_range(rows, ("F", 10, "F", 61))
    assert [r.source_cell for r in offenders] == ["F9"]


def test_import_budget_ignores_labeled_income_rows_outside_monthly_total_range(tmp_path: Path):
    workbook = build_budget_workbook(
        tmp_path / "Budget.xlsx",
        labeled_monthly_income=True,
    )
    database = Database(tmp_path / "test.db")
    database.initialize()

    summary = BudgetImporter(database).import_budget(workbook, "2026 Budget")

    assert summary["row_count"] == 11
    with database.connect() as connection:
        planned_rows = connection.execute(
            """
            SELECT group_name, category_name, block
            FROM v_latest_planned_categories
            ORDER BY id
            """
        ).fetchall()

    assert not any(
        row["block"] == "monthly" and row["category_name"] == "TherapyNotes"
        for row in planned_rows
    )


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


def test_import_first_run_records_no_revisions(tmp_path: Path):
    """No prior active plan, so the importer has nothing to snapshot."""
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    database = Database(tmp_path / "test.db")
    database.initialize()
    BudgetImporter(database).import_budget(workbook, "2026 Budget")
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_revisions"
        ).fetchone()["n"]
    assert count == 0


def test_reimport_snapshots_pre_archive_plan_for_restore(tmp_path: Path):
    """Edits made between two imports should survive as an importer
    revision tagged with the new plan_id, so the operator can restore
    them after a re-import overwrites the active plan."""
    from finclaide.plan_service import PlanService

    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    database = Database(tmp_path / "test.db")
    database.initialize()
    importer = BudgetImporter(database)

    importer.import_budget(workbook, "2026 Budget")
    plan_service = PlanService(database=database)

    plan = plan_service.get_active_plan()
    rent = next(
        c for c in plan["blocks"]["monthly"] if c["category_name"] == "Rent"
    )
    plan_service.update_category(
        plan["plan"]["id"], rent["id"], {"planned_milliunits": 1234567}
    )

    # Re-import: should snapshot the edited plan before archiving it.
    importer.import_budget(workbook, "2026 Budget")

    new_plan = plan_service.get_active_plan()
    new_plan_id = new_plan["plan"]["id"]
    revisions = plan_service.list_revisions(new_plan_id)
    importer_revs = [r for r in revisions if r["source"] == "importer"]
    assert len(importer_revs) == 1
    importer_rev = importer_revs[0]
    detail = plan_service.get_revision(importer_rev["id"])
    edited_in_snapshot = next(
        c for c in detail["snapshot"] if c["category_name"] == "Rent"
    )
    assert edited_in_snapshot["planned_milliunits"] == 1234567

    # The new active plan reflects the workbook (not the edit).
    new_rent = next(
        c for c in new_plan["blocks"]["monthly"] if c["category_name"] == "Rent"
    )
    assert new_rent["planned_milliunits"] != 1234567

    # Restore brings the edit back onto the new active plan.
    restored = plan_service.restore_revision(importer_rev["id"])
    restored_rent = next(
        c for c in restored["blocks"]["monthly"] if c["category_name"] == "Rent"
    )
    assert restored_rent["planned_milliunits"] == 1234567
