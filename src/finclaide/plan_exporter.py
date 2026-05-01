from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from finclaide.database import utc_now
from finclaide.plan_service import PlanService

# The importer in `budget_sheet.py` reads a fixed column layout. The
# exporter must match it cell-for-cell so the round-trip stays clean.
#
#   Monthly  → A:B    (group rows have empty B)
#   Yearly   → D:G    (group rows have empty E/F/G; G = monthly value;
#                      F = due month text; E = annual target)
#   Stipends → I:J    (group rows have empty J)
#   Savings  → L:M    (group rows have empty M)
#
# Totals live at row 53 (`B53`, `G53`, `J53`, `M53`) — matches the
# legacy fallback in `budget_sheet.py:369-397`. Totals carry `=SUM(...)`
# formulas with cached numeric values injected so the importer's
# `_required_total_value` validation passes.
TOTALS_ROW = 53

_MONTH_ABBREVIATIONS = (
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ET.register_namespace("", _NS_MAIN)


@dataclass
class ExportResult:
    bytes: bytes
    filename: str
    row_count: int


class PlanExporter:
    """Renders the active plan as an .xlsx matching `BudgetImporter`'s layout."""

    def __init__(self, plan_service: PlanService):
        self._plan_service = plan_service

    def export_active_plan(
        self,
        *,
        sheet_name: str,
        plan_year: int | None = None,
        now: str | None = None,
    ) -> ExportResult:
        plan = self._plan_service.get_active_plan(plan_year=plan_year)
        timestamp = now or utc_now()

        workbook = Workbook()
        worksheet = workbook.active
        assert worksheet is not None  # openpyxl always creates one
        worksheet.title = sheet_name

        cached_values: dict[str, int | float] = {}
        row_count = 0

        # --- Monthly block (A:B) --------------------------------------------
        monthly_total = self._write_monthly_block(
            worksheet, plan["blocks"]["monthly"]
        )
        row_count += len(plan["blocks"]["monthly"])
        worksheet["A" + str(TOTALS_ROW)] = "Total"
        worksheet["B" + str(TOTALS_ROW)] = "=SUM(B2:B52)"
        cached_values["B" + str(TOTALS_ROW)] = _milliunits_to_dollars(monthly_total)

        # --- Yearly + One-time block (D:G) ----------------------------------
        yearly_total = self._write_yearly_block(
            worksheet,
            annual_rows=plan["blocks"]["annual"],
            one_time_rows=plan["blocks"]["one_time"],
        )
        row_count += len(plan["blocks"]["annual"]) + len(
            plan["blocks"]["one_time"]
        )
        worksheet["D" + str(TOTALS_ROW)] = "Total"
        worksheet["G" + str(TOTALS_ROW)] = "=SUM(G2:G52)"
        cached_values["G" + str(TOTALS_ROW)] = _milliunits_to_dollars(yearly_total)

        # --- Stipends (I:J) -------------------------------------------------
        stipends_total = self._write_simple_block(
            worksheet,
            rows=plan["blocks"]["stipends"],
            name_col="I",
            amount_col="J",
            header_label="Stipends",
        )
        row_count += len(plan["blocks"]["stipends"])
        worksheet["I" + str(TOTALS_ROW)] = "Total"
        worksheet["J" + str(TOTALS_ROW)] = "=SUM(J2:J52)"
        cached_values["J" + str(TOTALS_ROW)] = _milliunits_to_dollars(stipends_total)

        # --- Savings (L:M) --------------------------------------------------
        savings_total = self._write_simple_block(
            worksheet,
            rows=plan["blocks"]["savings"],
            name_col="L",
            amount_col="M",
            header_label="Savings",
        )
        row_count += len(plan["blocks"]["savings"])
        worksheet["L" + str(TOTALS_ROW)] = "Total"
        worksheet["M" + str(TOTALS_ROW)] = "=SUM(M2:M52)"
        cached_values["M" + str(TOTALS_ROW)] = _milliunits_to_dollars(savings_total)

        # Currency format on amount columns. Skip the totals row's text
        # cell (only format the amount column).
        for column_letter in ("B", "E", "G", "J", "M"):
            for row in range(2, TOTALS_ROW + 1):
                cell = worksheet[f"{column_letter}{row}"]
                cell.number_format = "$#,##0.00"

        buffer = BytesIO()
        workbook.save(buffer)
        rendered_bytes = buffer.getvalue()

        # openpyxl can't compute formulas; inject cached values for the
        # totals so the importer's `_required_total_value` check passes
        # on a round-trip.
        rendered_bytes = _inject_cached_values(
            rendered_bytes, sheet_name, cached_values
        )

        plan_name = plan["plan"]["name"]
        suggested_filename = _build_suggested_filename(plan_name, timestamp)

        return ExportResult(
            bytes=rendered_bytes,
            filename=suggested_filename,
            row_count=row_count,
        )

    # --- block writers -----------------------------------------------------

    def _write_monthly_block(self, worksheet, rows: list[dict[str, Any]]) -> int:
        return self._write_simple_block(
            worksheet,
            rows=rows,
            name_col="A",
            amount_col="B",
            header_label=None,
        )

    def _write_simple_block(
        self,
        worksheet,
        *,
        rows: list[dict[str, Any]],
        name_col: str,
        amount_col: str,
        header_label: str | None,
    ) -> int:
        """Writes monthly/stipends/savings-shaped block (single name col + single amount col)."""
        if header_label is not None:
            worksheet[f"{name_col}1"] = header_label
        next_row = 2
        current_group: str | None = None
        block_total = 0
        for row in rows:
            if row["group_name"] != current_group:
                worksheet[f"{name_col}{next_row}"] = row["group_name"]
                # Amount cell stays empty → matches importer's group-row
                # detection (`amount_value in (None, "")`).
                next_row += 1
                current_group = row["group_name"]
            worksheet[f"{name_col}{next_row}"] = row["category_name"]
            worksheet[f"{amount_col}{next_row}"] = _milliunits_to_dollars(
                row["planned_milliunits"]
            )
            block_total += int(row["planned_milliunits"])
            next_row += 1
        return block_total

    def _write_yearly_block(
        self,
        worksheet,
        *,
        annual_rows: list[dict[str, Any]],
        one_time_rows: list[dict[str, Any]],
    ) -> int:
        """Writes the yearly + one-time block at columns D:G.

        Group header rows have empty E/F/G (matches importer's
        `_is_yearly_group_header`). Category rows have:
            E = annual_target ($)
            F = due-month text (e.g. "Jun") or empty
            G = monthly amount ($)
        """
        next_row = 2
        block_total = 0
        for current_group, group_rows in (
            ("Yearly", annual_rows),
            ("One Time Purchase", one_time_rows),
        ):
            if not group_rows:
                continue
            worksheet[f"D{next_row}"] = current_group
            next_row += 1
            for row in group_rows:
                worksheet[f"D{next_row}"] = row["category_name"]
                worksheet[f"E{next_row}"] = _milliunits_to_dollars(
                    row.get("annual_target_milliunits", 0)
                )
                due_month = row.get("due_month")
                if due_month:
                    worksheet[f"F{next_row}"] = _MONTH_ABBREVIATIONS[int(due_month)]
                worksheet[f"G{next_row}"] = _milliunits_to_dollars(
                    row["planned_milliunits"]
                )
                block_total += int(row["planned_milliunits"])
                next_row += 1
        return block_total


def _milliunits_to_dollars(milliunits: int | None) -> float:
    if milliunits is None:
        return 0.0
    return round(int(milliunits) / 1000, 2)


def _build_suggested_filename(plan_name: str, timestamp: str) -> str:
    # Strip filesystem-unfriendly characters; we keep spaces because the
    # browser download dialog lets users rename anyway, and the source
    # name (e.g. "2026 Budget") reads nicer with a space.
    safe = re.sub(r"[\\/:*?\"<>|]", "_", plan_name)
    stamp = re.sub(r"[^0-9TZ:.-]", "", timestamp.replace("+00:00", ""))[:16]
    stamp = stamp.replace(":", "")
    return f"{safe} — exported {stamp}.xlsx"


def _inject_cached_values(
    rendered_bytes: bytes,
    sheet_name: str,
    values: dict[str, int | float],
) -> bytes:
    """Patch cached numeric values onto the formula cells in the rendered
    workbook so the importer's `_required_total_value` validation works.

    openpyxl writes formulas without any cached result, but `BudgetImporter`
    requires `cached_value` to be set on every "Total" row formula cell.
    This rewrites the underlying sheet XML in-place to inject `<v>` values.
    Same trick the test workbook builder uses (`tests/workbook_builder.py:212`).
    """
    if not values:
        return rendered_bytes
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir, "patched.xlsx")
        source_path = Path(temp_dir, "source.xlsx")
        source_path.write_bytes(rendered_bytes)
        with zipfile.ZipFile(source_path) as source_zip:
            source_zip.extractall(temp_dir)

        workbook_xml = ET.parse(Path(temp_dir, "xl", "workbook.xml"))
        rels_xml = ET.parse(Path(temp_dir, "xl", "_rels", "workbook.xml.rels"))
        relationship_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_xml.getroot().findall(f"{{{_NS_REL}}}Relationship")
        }
        target_path: str | None = None
        sheets_node = workbook_xml.getroot().find(f"{{{_NS_MAIN}}}sheets")
        if sheets_node is None:
            raise RuntimeError("Rendered workbook is missing <sheets> node.")
        for sheet in sheets_node:
            if sheet.attrib["name"] == sheet_name:
                target_path = relationship_map[sheet.attrib[f"{{{_NS_DOC_REL}}}id"]]
                break
        if target_path is None:
            raise RuntimeError(
                f"Sheet '{sheet_name}' not found in rendered workbook — "
                "exporter is misconfigured."
            )
        normalized = target_path.lstrip("/")
        if not normalized.startswith("xl/"):
            normalized = f"xl/{normalized}"
        sheet_path = Path(temp_dir, normalized)
        sheet_tree = ET.parse(sheet_path)
        cells = {
            cell.attrib["r"]: cell
            for cell in sheet_tree.getroot().findall(f".//{{{_NS_MAIN}}}c")
        }
        for ref, cached in values.items():
            cell = cells.get(ref)
            if cell is None:
                # Cell exists in the workbook (we wrote a formula there)
                # but the XML serializer may have written it under a
                # different row container — the dict lookup should be
                # exhaustive. Fail loud so a regression is obvious.
                raise RuntimeError(
                    f"Could not find cell {ref} in rendered sheet XML."
                )
            value_node = cell.find(f"{{{_NS_MAIN}}}v")
            if value_node is None:
                value_node = ET.SubElement(cell, f"{{{_NS_MAIN}}}v")
            value_node.text = str(cached)
        sheet_tree.write(sheet_path, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            for path in Path(temp_dir).rglob("*"):
                if path == temp_path or path == source_path or path.is_dir():
                    continue
                output_zip.write(path, path.relative_to(temp_dir))
        return temp_path.read_bytes()


def load_exported_workbook_for_test(content: bytes):
    """Test helper: load rendered xlsx bytes via openpyxl with formulas
    visible. Tests use this to assert cell values + formulas without
    re-running the importer."""
    return load_workbook(BytesIO(content), data_only=False)
