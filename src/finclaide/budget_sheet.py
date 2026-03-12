from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

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
        max_row = sheet_formula.max_row

        plan_year = self._extract_plan_year(sheet_name)
        rows = []
        rows.extend(self._parse_monthly_block(sheet_formula, sheet_cached))
        rows.extend(self._parse_yearly_block(sheet_formula, sheet_cached))
        rows.extend(self._parse_single_group_block(sheet_formula, sheet_cached, "I", "J", 2, max_row, "Stipends"))
        rows.extend(self._parse_single_group_block(sheet_formula, sheet_cached, "L", "M", 2, max_row, "Savings"))

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
        current_group: str | None = None
        for row_number in range(2, sheet_formula.max_row + 1):
            name_cell = f"A{row_number}"
            amount_cell = f"B{row_number}"
            name_value = self._text_value(sheet_formula[name_cell].value)
            amount_value = sheet_cached[amount_cell].value
            if not name_value:
                continue
            if self._is_summary_label(name_value):
                break
            if amount_value in (None, ""):
                current_group = name_value
                continue
            if current_group is None:
                continue
            formula_text = self._formula_text(sheet_formula[amount_cell].value)
            rows.append(
                PlannedCategoryRow(
                    group_name=current_group,
                    category_name=name_value,
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
        current_group: str | None = None
        for row_number in range(2, sheet_formula.max_row + 1):
            name_cell = f"D{row_number}"
            total_cell = f"E{row_number}"
            due_cell = f"F{row_number}"
            monthly_cell = f"G{row_number}"
            name_value = self._text_value(sheet_formula[name_cell].value)
            total_value = sheet_cached[total_cell].value
            due_value = self._text_value(sheet_formula[due_cell].value)
            due_or_monthly_value = sheet_cached[due_cell].value
            monthly_value = sheet_cached[monthly_cell].value
            if not name_value:
                continue
            if self._is_summary_label(name_value):
                break
            if self._is_yearly_group_header(total_value, due_or_monthly_value, monthly_value):
                current_group = name_value
                continue
            if current_group is None:
                continue
            planned_value, source_cell = self._resolve_yearly_planned_value(
                row_number=row_number,
                due_or_monthly_value=due_or_monthly_value,
                monthly_value=monthly_value,
            )
            rows.append(
                PlannedCategoryRow(
                    group_name=current_group,
                    category_name=name_value,
                    block="annual" if current_group == "Yearly" else "one_time",
                    source_cell=source_cell,
                    planned_milliunits=to_milliunits(planned_value),
                    annual_target_milliunits=to_milliunits(total_value),
                    due_month=parse_due_month(due_value) or parse_due_month(name_value),
                    formula_text=self._formula_text(sheet_formula[source_cell].value),
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
        name_column = self._find_header_column(sheet_formula, expected_group, [name_column, chr(ord(name_column) - 1)])
        amount_column = get_column_letter(ord(name_column) - 64 + 1)
        group_value = self._text_value(sheet_formula[f"{name_column}1"].value)
        rows: list[PlannedCategoryRow] = []
        current_group: str | None = group_value
        for row_number in range(start_row, end_row + 1):
            name_cell = f"{name_column}{row_number}"
            amount_cell = f"{amount_column}{row_number}"
            name_value = self._text_value(sheet_formula[name_cell].value)
            amount_value = sheet_cached[amount_cell].value
            if not name_value:
                continue
            if self._is_summary_label(name_value):
                break
            if amount_value in (None, ""):
                current_group = name_value
                continue
            if current_group is None:
                raise DataIntegrityError(f"Missing group header before {name_cell}.")
            rows.append(
                PlannedCategoryRow(
                    group_name=current_group,
                    category_name=name_value,
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
            "monthly": to_milliunits(
                self._required_total_value(
                    sheet_formula,
                    sheet_cached,
                    label_columns=["A"],
                    amount_columns=["B"],
                    legacy_cell="B53",
                )
            ),
            "annual": to_milliunits(
                self._required_total_value(
                    sheet_formula,
                    sheet_cached,
                    label_columns=["D", "E", "F"],
                    amount_columns=["E", "F", "G"],
                    legacy_cell="G53",
                )
            ),
            "stipends": to_milliunits(
                self._required_total_value(
                    sheet_formula,
                    sheet_cached,
                    label_columns=["H", "I"],
                    amount_columns=["I", "J"],
                    legacy_cell="J53",
                )
            ),
            "savings": to_milliunits(
                self._required_total_value(
                    sheet_formula,
                    sheet_cached,
                    label_columns=["K", "L"],
                    amount_columns=["L", "M"],
                    legacy_cell="M53",
                )
            ),
        }
        mismatches = [
            f"{name}: expected {expected[name]}, got {totals[name]}"
            for name in totals
            if abs(totals[name] - expected[name]) > self.TOTAL_TOLERANCE_MILLIUNITS
        ]
        if mismatches:
            raise DataIntegrityError("Budget totals do not match cached formulas: " + "; ".join(mismatches))

    def _required_total_value(
        self,
        sheet_formula,
        sheet_cached,
        *,
        label_columns: list[str],
        amount_columns: list[str],
        legacy_cell: str,
    ):
        for row_number in range(1, sheet_formula.max_row + 1):
            if not any(
                self._text_value(sheet_formula[f"{column}{row_number}"].value) == "Total"
                for column in label_columns
            ):
                continue
            for amount_column in amount_columns:
                cell_ref = f"{amount_column}{row_number}"
                formula_value = sheet_formula[cell_ref].value
                cached_value = sheet_cached[cell_ref].value
                if isinstance(formula_value, str) and formula_value.startswith("="):
                    if cached_value is None:
                        raise DataIntegrityError(f"Missing cached formula result in {cell_ref}.")
                    return cached_value
        return self._required_cached_value(sheet_formula, sheet_cached, legacy_cell)

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

    def _find_header_column(self, sheet_formula, expected_group: str, candidates: list[str]) -> str:
        for column in candidates:
            if self._text_value(sheet_formula[f"{column}1"].value) == expected_group:
                return column
        raise DataIntegrityError(f"Expected {expected_group!r} header in row 1.")

    def _is_yearly_group_header(self, total_value: Any, due_or_monthly_value: Any, monthly_value: Any) -> bool:
        return (
            self._numeric_value(total_value) is None
            and self._numeric_value(due_or_monthly_value) is None
            and self._numeric_value(monthly_value) is None
        )

    def _resolve_yearly_planned_value(
        self,
        *,
        row_number: int,
        due_or_monthly_value: Any,
        monthly_value: Any,
    ) -> tuple[Any, str]:
        if self._numeric_value(monthly_value) is not None:
            return monthly_value, f"G{row_number}"
        if self._numeric_value(due_or_monthly_value) is not None:
            return due_or_monthly_value, f"F{row_number}"
        raise DataIntegrityError(f"Missing annual planned amount at F{row_number}.")

    def _numeric_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        return None

    def _text_value(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _is_summary_label(self, value: str) -> bool:
        return value in {"Total", "Remaining"}

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
