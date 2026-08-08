from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.services.spreadsheets.normalization import clean_text


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PACKAGE_REL_NS}


class SpreadsheetParseError(Exception):
    pass


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result


def column_letter(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def resolve_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


@dataclass
class MergeRange:
    min_row: int
    max_row: int
    min_column: int
    max_column: int

    def contains(self, row: int, column: int) -> bool:
        return self.min_row <= row <= self.max_row and self.min_column <= column <= self.max_column


@dataclass
class SheetData:
    name: str
    path: str
    rows: dict[int, dict[int, object]] = field(default_factory=dict)
    max_row: int = 0
    max_column: int = 0
    merges: list[MergeRange] = field(default_factory=list)
    drawing_paths: list[str] = field(default_factory=list)

    def value(self, row: int, column: int, merged: bool = True) -> object | None:
        direct = self.rows.get(row, {}).get(column)
        if direct not in (None, "") or not merged:
            return direct
        for area in self.merges:
            if area.contains(row, column):
                return self.rows.get(area.min_row, {}).get(area.min_column)
        return direct

    def row_values(self, row: int, merged: bool = True) -> dict[int, object]:
        values = dict(self.rows.get(row, {}))
        if merged:
            for area in self.merges:
                if area.min_row <= row <= area.max_row:
                    value = self.rows.get(area.min_row, {}).get(area.min_column)
                    if value not in (None, ""):
                        for column in range(area.min_column, area.max_column + 1):
                            values.setdefault(column, value)
        return values


@dataclass
class WorkbookData:
    archive: ZipFile
    sheets: list[SheetData]

    def close(self) -> None:
        self.archive.close()

    def __enter__(self) -> "WorkbookData":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(f".//{{{MAIN_NS}}}t")) for item in root]


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> object | None:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{MAIN_NS}}}t"))
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None:
        return None
    value = value_node.text or ""
    if kind == "s" and value:
        try:
            return shared[int(value)]
        except (IndexError, ValueError) as exc:
            raise SpreadsheetParseError("Índice de texto compartilhado inválido.") from exc
    if kind in {"str", "e"}:
        return value
    if kind == "b":
        return value == "1"
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value


def _merge_range(reference: str) -> MergeRange:
    start, end = (reference.split(":", 1) + [reference])[:2]
    start_row = int(re.search(r"\d+", start).group())
    end_row = int(re.search(r"\d+", end).group())
    return MergeRange(start_row, end_row, column_number(start), column_number(end))


def _relationships(archive: ZipFile, rels_path: str) -> dict[str, str]:
    if rels_path not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(rels_path))
    return {
        item.attrib["Id"]: item.attrib["Target"]
        for item in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        if "Id" in item.attrib and "Target" in item.attrib
    }


def load_workbook(path: Path) -> WorkbookData:
    try:
        archive = ZipFile(path)
        shared = _shared_strings(archive)
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        workbook_rels = _relationships(archive, "xl/_rels/workbook.xml.rels")
        sheets: list[SheetData] = []
        for sheet_node in workbook.findall(".//m:sheet", NS):
            relation_id = sheet_node.attrib.get(f"{{{REL_NS}}}id")
            if not relation_id or relation_id not in workbook_rels:
                continue
            sheet_path = resolve_target("xl/workbook.xml", workbook_rels[relation_id])
            root = ElementTree.fromstring(archive.read(sheet_path))
            data = SheetData(name=sheet_node.attrib["name"], path=sheet_path)
            for row_node in root.findall(".//m:sheetData/m:row", NS):
                row_number = int(row_node.attrib.get("r", "0"))
                row: dict[int, object] = {}
                for cell in row_node.findall("m:c", NS):
                    reference = cell.attrib.get("r", "")
                    column = column_number(reference)
                    value = _cell_value(cell, shared)
                    if column and value not in (None, ""):
                        row[column] = value
                        data.max_column = max(data.max_column, column)
                if row:
                    data.rows[row_number] = row
                    data.max_row = max(data.max_row, row_number)
            for merge in root.findall(".//m:mergeCells/m:mergeCell", NS):
                if reference := merge.attrib.get("ref"):
                    data.merges.append(_merge_range(reference))
            sheet_rels_path = posixpath.join(posixpath.dirname(sheet_path), "_rels", posixpath.basename(sheet_path) + ".rels")
            sheet_rels = _relationships(archive, sheet_rels_path)
            for drawing in root.findall(".//m:drawing", NS):
                relation_id = drawing.attrib.get(f"{{{REL_NS}}}id")
                if relation_id in sheet_rels:
                    data.drawing_paths.append(resolve_target(sheet_path, sheet_rels[relation_id]))
            sheets.append(data)
        return WorkbookData(archive=archive, sheets=sheets)
    except (BadZipFile, KeyError, OSError, ElementTree.ParseError) as exc:
        try:
            archive.close()
        except UnboundLocalError:
            pass
        raise SpreadsheetParseError("Não foi possível interpretar a estrutura do XLSX.") from exc
