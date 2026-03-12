from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from finclaide.database import Database, utc_now
from finclaide.errors import DataIntegrityError
from finclaide.money import to_milliunits
from finclaide.months import parse_due_month


@dataclass(frozen=True)
class PlannedCategoryRow:
    group_name: str
    category_name: str
    block: str
    source_cell: str
    planned_milliunits: int
    annual_target_milliunits: int
    due_month: int | None
    formula_text: str | None


class BudgetImporter:
    TOTAL_TOLERANCE_MILLIUNITS = 10

    def __init__(self, database: Database) -> None:
        self.database = database

    def import_budget(self, workbook_path: Path, sheet_name: str) -> dict[str, object]:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            raise DataIntegrityError(f"Workbook not found at {workbook_path}")

        workbook_formula = load_workbook(workbook_path, data_only=False)
        workbook_cached = load_workbook(workbook_path, data_only=True)
        if sheet_name not in workbook_formula.sheetnames:
            raise DataIntegrityError(f"Required sheet '{sheet_name}' not found in workbook.")

        sheet_formula = workbook_formula[sheet_name]
        sheet_cached = workbook_cached[sheet_name]

        plan_year = self._extract_plan_year(sheet_name)
        rows = []
        rows.extend(self._parse_monthly_block(sheet_formula, sheet_cached))
        rows.extend(self._parse_yearly_block(sheet_formula, sheet_cached))
        rows.extend(self._parse_single_group_block(sheet_formula, sheet_cached, "I", "J", 2, 51, "Stipends"))
        rows.extend(self._parse_single_group_block(sheet_formula, sheet_cached, "L", "M", 2, 51, "Savings"))

        duplicates = self._find_duplicates(rows)
        if duplicates:
            raise DataIntegrityError(
                f"Duplicate planned categories detected: {', '.join(sorted(duplicates))}"
            )

        self._validate_totals(sheet_formula, sheet_cached, rows)

        digest = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
        summary = {
            "imported_at": utc_now(),
            "plan_year": plan_year,
            "row_count": len(rows),
            "groups": sorted({row.group_name for row in rows}),
        }

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO budget_imports(workbook_path, workbook_sha256, sheet_name, imported_at, plan_year, summary_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(workbook_path),
                    digest,
                    sheet_name,
                    summary["imported_at"],
                    plan_year,
                    json.dumps(summary, sort_keys=True),
                ),
            )
            import_id = int(cursor.lastrowid)
            group_ids: dict[str, int] = {}
            for group_name, block in sorted({(row.group_name, row.block) for row in rows}):
                group_cursor = connection.execute(
                    """
                    INSERT INTO planned_groups(import_id, name, block)
                    VALUES (?, ?, ?)
                    """,
                    (import_id, group_name, block),
                )
                group_ids[group_name] = int(group_cursor.lastrowid)

            for row in rows:
                connection.execute(
                    """
                    INSERT INTO planned_categories(
                        import_id,
                        planned_group_id,
                        group_name,
                        category_name,
                        block,
                        source_cell,
                        planned_milliunits,
                        annual_target_milliunits,
                        due_month,
                        formula_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_id,
                        group_ids[row.group_name],
                        row.group_name,
                        row.category_name,
                        row.block,
                        row.source_cell,
                        row.planned_milliunits,
                        row.annual_target_milliunits,
                        row.due_month,
                        row.formula_text,
                    ),
                )

        summary["import_id"] = import_id
        return summary

    def _parse_monthly_block(self, sheet_formula, sheet_cached) -> list[PlannedCategoryRow]:
        rows: list[PlannedCategoryRow] = []
        current_group = sheet_formula["A2"].value
        if not current_group:
            raise DataIntegrityError("Expected monthly group header in A2.")
        for row_number in range(5, 52):
            name_cell = f"A{row_number}"
            amount_cell = f"B{row_number}"
            name_value = sheet_formula[name_cell].value
            amount_value = sheet_cached[amount_cell].value
            if name_value and amount_value in (None, ""):
                current_group = str(name_value).strip()
                continue
            if not name_value:
                continue
            if amount_value is None:
                raise DataIntegrityError(f"Missing monthly planned amount at {amount_cell}.")
            formula_text = self._formula_text(sheet_formula[amount_cell].value)
            rows.append(
                PlannedCategoryRow(
                    group_name=str(current_group).strip(),
                    category_name=str(name_value).strip(),
                    block="monthly",
                    source_cell=amount_cell,
                    planned_milliunits=to_milliunits(amount_value),
                    annual_target_milliunits=to_milliunits(amount_value),
                    due_month=None,
                    formula_text=formula_text,
                )
            )
        return rows

    def _parse_yearly_block(self, sheet_formula, sheet_cached) -> list[PlannedCategoryRow]:
        rows: list[PlannedCategoryRow] = []
        current_group = str(sheet_formula["D7"].value or sheet_formula["D1"].value or "").strip()
        if not current_group:
            raise DataIntegrityError("Expected yearly block group header in D7 or D1.")
        for row_number in range(8, 52):
            name_cell = f"D{row_number}"
            total_cell = f"E{row_number}"
            due_cell = f"F{row_number}"
            monthly_cell = f"G{row_number}"
            name_value = sheet_formula[name_cell].value
            total_value = sheet_cached[total_cell].value
            monthly_value = sheet_cached[monthly_cell].value
            due_value = sheet_formula[due_cell].value
            if name_value and total_value in (None, "") and monthly_value in (None, ""):
                current_group = str(name_value).strip()
                continue
            if not name_value:
                continue
            if monthly_value is None:
                raise DataIntegrityError(f"Missing annual planned amount at {monthly_cell}.")
            rows.append(
                PlannedCategoryRow(
                    group_name=current_group,
                    category_name=str(name_value).strip(),
                    block="annual" if current_group == "Yearly" else "one_time",
                    source_cell=monthly_cell,
                    planned_milliunits=to_milliunits(monthly_value),
                    annual_target_milliunits=to_milliunits(total_value),
                    due_month=parse_due_month(str(due_value)) if due_value else None,
                    formula_text=self._formula_text(sheet_formula[monthly_cell].value),
                )
            )
        return rows

    def _parse_single_group_block(
        self,
        sheet_formula,
        sheet_cached,
        name_column: str,
        amount_column: str,
        start_row: int,
        end_row: int,
        expected_group: str,
    ) -> list[PlannedCategoryRow]:
        group_value = str(sheet_formula[f"{name_column}1"].value or "").strip()
        if group_value != expected_group:
            raise DataIntegrityError(
                f"Expected {expected_group!r} header in {name_column}1, found {group_value!r}."
            )
        rows: list[PlannedCategoryRow] = []
        for row_number in range(start_row, end_row + 1):
            name_cell = f"{name_column}{row_number}"
            amount_cell = f"{amount_column}{row_number}"
            name_value = sheet_formula[name_cell].value
            amount_value = sheet_cached[amount_cell].value
            if not name_value:
                continue
            if amount_value is None:
                raise DataIntegrityError(f"Missing planned amount at {amount_cell}.")
            rows.append(
                PlannedCategoryRow(
                    group_name=expected_group,
                    category_name=str(name_value).strip(),
                    block=expected_group.lower(),
                    source_cell=amount_cell,
                    planned_milliunits=to_milliunits(amount_value),
                    annual_target_milliunits=to_milliunits(amount_value),
                    due_month=None,
                    formula_text=self._formula_text(sheet_formula[amount_cell].value),
                )
            )
        return rows

    def _validate_totals(
        self,
        sheet_formula,
        sheet_cached,
        rows: list[PlannedCategoryRow],
    ) -> None:
        totals = {
            "monthly": sum(row.planned_milliunits for row in rows if row.block == "monthly"),
            "annual": sum(
                row.planned_milliunits
                for row in rows
                if row.block in {"annual", "one_time"}
            ),
            "stipends": sum(row.planned_milliunits for row in rows if row.block == "stipends"),
            "savings": sum(row.planned_milliunits for row in rows if row.block == "savings"),
        }
        expected = {
            "monthly": to_milliunits(self._required_cached_value(sheet_formula, sheet_cached, "B53")),
            "annual": to_milliunits(self._required_cached_value(sheet_formula, sheet_cached, "G53")),
            "stipends": to_milliunits(self._required_cached_value(sheet_formula, sheet_cached, "J53")),
            "savings": to_milliunits(self._required_cached_value(sheet_formula, sheet_cached, "M53")),
        }
        mismatches = [
            f"{name}: expected {expected[name]}, got {totals[name]}"
            for name in totals
            if abs(totals[name] - expected[name]) > self.TOTAL_TOLERANCE_MILLIUNITS
        ]
        if mismatches:
            raise DataIntegrityError("Budget totals do not match cached formulas: " + "; ".join(mismatches))

    def _required_cached_value(self, sheet_formula, sheet_cached, cell_ref: str):
        formula_value = sheet_formula[cell_ref].value
        cached_value = sheet_cached[cell_ref].value
        if formula_value is None or not isinstance(formula_value, str) or not formula_value.startswith("="):
            raise DataIntegrityError(f"Expected formula in {cell_ref}.")
        if cached_value is None:
            raise DataIntegrityError(f"Missing cached formula result in {cell_ref}.")
        return cached_value

    def _formula_text(self, cell_value) -> str | None:
        if isinstance(cell_value, str) and cell_value.startswith("="):
            return cell_value
        return None

    def _find_duplicates(self, rows: list[PlannedCategoryRow]) -> set[str]:
        seen: set[tuple[str, str]] = set()
        duplicates: set[str] = set()
        for row in rows:
            key = (row.group_name, row.category_name)
            if key in seen:
                duplicates.add(f"{row.group_name}/{row.category_name}")
            seen.add(key)
        return duplicates

    def _extract_plan_year(self, sheet_name: str) -> int:
        match = re.search(r"(20\d{2})", sheet_name)
        if not match:
            raise DataIntegrityError(f"Could not infer plan year from sheet name {sheet_name!r}.")
        return int(match.group(1))
