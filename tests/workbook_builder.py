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
) -> Path:
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
