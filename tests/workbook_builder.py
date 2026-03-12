from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from openpyxl import Workbook


NAMESPACE_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NAMESPACE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NAMESPACE_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

ET.register_namespace("", NAMESPACE_MAIN)


def build_budget_workbook(
    destination: Path,
    *,
    duplicate_category: bool = False,
    missing_cached_formula: bool = False,
    wrong_sheet_name: bool = False,
    invalid_layout: bool = False,
    layout: str = "legacy",
) -> Path:
    if layout == "current":
        return build_current_budget_workbook(
            destination,
            wrong_sheet_name=wrong_sheet_name,
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Wrong Sheet" if wrong_sheet_name else "2026 Budget"

    sheet["A1"] = "Monthly Budget"
    sheet["A2"] = "Bills"
    sheet["B3"] = "=3000"
    sheet["A5"] = "Rent"
    sheet["B5"] = 1000
    sheet["A6"] = "Rent" if duplicate_category else "Utilities"
    sheet["B6"] = 200
    sheet["A21"] = "Expenses"
    sheet["A22"] = "Groceries"
    sheet["B22"] = 300
    sheet["A23"] = "Fuel"
    sheet["B23"] = 150
    sheet["B53"] = "=SUM(B5:B51)"
    sheet["B54"] = "=B3-B53"

    sheet["D1"] = "Yearly/One-time"
    sheet["E1"] = "Yearly Total"
    sheet["F1"] = "Month"
    sheet["G1"] = "=B54"
    sheet["D7"] = "Yearly"
    sheet["D8"] = "Vacation"
    sheet["E8"] = 1200
    sheet["F8"] = "Jun"
    sheet["G8"] = "=E8/12"
    sheet["D9"] = "Insurance"
    sheet["E9"] = 600
    sheet["F9"] = "Dec"
    sheet["G9"] = "=E9/12"
    sheet["D43"] = "One Time Purchase"
    sheet["D44"] = "Laptop"
    sheet["G44"] = 75
    sheet["G53"] = "=SUM(G8:G51)"
    sheet["G54"] = "=G1-G53"

    sheet["I1"] = "Broken" if invalid_layout else "Stipends"
    sheet["I2"] = "S Stipend"
    sheet["J2"] = 100
    sheet["I3"] = "T Stipend"
    sheet["J3"] = 50
    sheet["J53"] = "=SUM(J2:J51)"
    sheet["J54"] = "=J1-J53"

    sheet["L1"] = "Savings"
    sheet["L2"] = "Emergency"
    sheet["M2"] = 200
    sheet["L3"] = "Investments"
    sheet["M3"] = 75
    sheet["M53"] = "=SUM(M2:M51)"
    sheet["M54"] = "=M1-M53"

    sheet["O1"] = "Discussion Items"
    sheet["P1"] = "Ignored"

    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)

    cached_values = {
        "B3": 3000,
        "B53": 1650,
        "B54": 1350,
        "G1": 1350,
        "G8": 100,
        "G9": 50,
        "G53": 225,
        "G54": 1125,
        "J53": 150,
        "J54": -150,
        "M53": 275,
        "M54": -275,
    }
    if missing_cached_formula:
        cached_values.pop("G53")
    inject_cached_values(destination, sheet.title, cached_values)
    return destination


def build_current_budget_workbook(
    destination: Path,
    *,
    wrong_sheet_name: bool = False,
) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Wrong Sheet" if wrong_sheet_name else "2026 Budget"

    sheet["A1"] = "Monthly Income"
    sheet["A2"] = "Salary"
    sheet["B2"] = "=3000"
    sheet["A4"] = "Bills"
    sheet["A5"] = "Rent"
    sheet["B5"] = 1000
    sheet["A6"] = "Utilities"
    sheet["B6"] = 200
    sheet["A8"] = "Expenses"
    sheet["A9"] = "Groceries"
    sheet["B9"] = 300
    sheet["A10"] = "Fuel"
    sheet["B10"] = 150
    sheet["A11"] = "Payments"
    sheet["A12"] = "Credit Card"
    sheet["B12"] = 100
    sheet["A20"] = "Total"
    sheet["B20"] = "=SUM(B5:B12)"
    sheet["A21"] = "Remaining"
    sheet["B21"] = "=B2-B20"

    sheet["D1"] = "Yearly Income"
    sheet["D2"] = "Bonus"
    sheet["E2"] = 1200
    sheet["F2"] = "=E2/12"
    sheet["D4"] = "Yearly"
    sheet["D5"] = "Feb - YNAB"
    sheet["E5"] = 120
    sheet["F5"] = "=E5/12"
    sheet["D6"] = "Dec - Insurance"
    sheet["E6"] = 600
    sheet["F6"] = "=E6/12"
    sheet["D8"] = "One Time Purchase"
    sheet["D9"] = "Laptop"
    sheet["F9"] = 75
    sheet["E20"] = "Total"
    sheet["F20"] = "=SUM(F5:F9)"
    sheet["E21"] = "Remaining"
    sheet["F21"] = "=F2-F20"

    sheet["H1"] = "Stipends"
    sheet["H2"] = "S Stipend"
    sheet["I2"] = 100
    sheet["H3"] = "T Stipend"
    sheet["I3"] = 50
    sheet["H5"] = "Fun"
    sheet["H6"] = "Soda"
    sheet["I6"] = 25
    sheet["H20"] = "Total"
    sheet["I20"] = "=SUM(I2:I6)"
    sheet["H21"] = "Remaining"
    sheet["I21"] = "=250-I20"

    sheet["K1"] = "Savings"
    sheet["K2"] = "Emergency"
    sheet["L2"] = 200
    sheet["K3"] = "Investments"
    sheet["L3"] = 75
    sheet["K20"] = "Total"
    sheet["L20"] = "=SUM(L2:L3)"
    sheet["K21"] = "Remaining"
    sheet["L21"] = "=300-L20"

    sheet["N1"] = "Discussion Items"
    sheet["O1"] = "Ignored"

    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)

    cached_values = {
        "B2": 3000,
        "B20": 1750,
        "B21": 1250,
        "F2": 100,
        "F5": 10,
        "F6": 50,
        "F20": 135,
        "F21": -35,
        "I20": 175,
        "I21": 75,
        "L20": 275,
        "L21": 25,
    }
    inject_cached_values(destination, sheet.title, cached_values)
    return destination


def inject_cached_values(workbook_path: Path, sheet_name: str, values: dict[str, int | float]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir, "patched.xlsx")
        with zipfile.ZipFile(workbook_path) as source_zip:
            source_zip.extractall(temp_dir)

        workbook_xml = ET.parse(Path(temp_dir, "xl", "workbook.xml"))
        workbook_root = workbook_xml.getroot()
        rels_xml = ET.parse(Path(temp_dir, "xl", "_rels", "workbook.xml.rels"))
        rels_root = rels_xml.getroot()
        relationship_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall(f"{{{NAMESPACE_REL}}}Relationship")
        }
        target_path = None
        for sheet in workbook_root.find(f"{{{NAMESPACE_MAIN}}}sheets"):
            if sheet.attrib["name"] == sheet_name:
                rid = sheet.attrib[f"{{{NAMESPACE_DOC_REL}}}id"]
                target_path = relationship_map[rid]
                break
        if target_path is None:
            raise AssertionError(f"Sheet {sheet_name!r} not found in workbook.")

        normalized_target = target_path.lstrip("/")
        if not normalized_target.startswith("xl/"):
            normalized_target = f"xl/{normalized_target}"
        sheet_xml_path = Path(temp_dir, normalized_target)
        sheet_tree = ET.parse(sheet_xml_path)
        root = sheet_tree.getroot()
        cells = {
            cell.attrib["r"]: cell
            for cell in root.findall(f".//{{{NAMESPACE_MAIN}}}c")
        }
        for ref, cached_value in values.items():
            cell = cells[ref]
            value_node = cell.find(f"{{{NAMESPACE_MAIN}}}v")
            if value_node is None:
                value_node = ET.SubElement(cell, f"{{{NAMESPACE_MAIN}}}v")
            value_node.text = str(cached_value)
        sheet_tree.write(sheet_xml_path, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            for file_path in Path(temp_dir).rglob("*"):
                if file_path == temp_path or file_path.is_dir():
                    continue
                output_zip.write(file_path, file_path.relative_to(temp_dir))
        workbook_path.write_bytes(temp_path.read_bytes())
