from __future__ import annotations

from dataclasses import dataclass, field

from app.services.spreadsheets.normalization import clean_text, header_role, is_code_candidate, is_ncm
from app.services.spreadsheets.parser import SheetData


ROLE_WEIGHTS = {
    "code": 7.0,
    "image": 3.0,
    "item_name": 3.0,
    "ncm": 3.0,
    "composition": 2.5,
    "construction": 2.0,
    "wash_label": 2.0,
    "hangtag": 2.0,
    "manufacturer": 1.5,
    "supplier": 1.5,
    "color": 1.0,
    "size": 1.0,
    "brand": 1.0,
    "packing_info": 0.5,
}


@dataclass
class DetectedSheet:
    sheet: SheetData
    header_rows: list[int] = field(default_factory=list)
    repeated_header_rows: set[int] = field(default_factory=set)
    column_roles: dict[int, str] = field(default_factory=dict)
    header_values: dict[int, str] = field(default_factory=dict)
    header_score: float = 0.0
    code_column: int | None = None
    code_header: str | None = None
    code_confidence: float = 0.0

    @property
    def data_start_row(self) -> int:
        return (max(self.header_rows) + 1) if self.header_rows else 1


def _combined_headers(sheet: SheetData, start_row: int, span: int) -> dict[int, str]:
    result: dict[int, str] = {}
    for column in range(1, sheet.max_column + 1):
        parts = []
        for row in range(start_row, min(start_row + span, sheet.max_row + 1)):
            value = clean_text(sheet.value(row, column))
            if value and value not in parts:
                parts.append(value)
        if parts:
            result[column] = " ".join(parts)
    return result


def _score_headers(values: dict[int, str]) -> tuple[float, dict[int, str]]:
    roles: dict[int, str] = {}
    used_roles: set[str] = set()
    score = 0.0
    for column, value in values.items():
        role, confidence = header_role(value)
        if role:
            roles[column] = role
            if role not in used_roles:
                used_roles.add(role)
                score += ROLE_WEIGHTS.get(role, 1.0) * confidence
    if "code" not in used_roles:
        score *= 0.72
    return score, roles


def _infer_column(sheet: SheetData, start_row: int, predicate) -> tuple[int | None, float]:
    best_column = None
    best_score = 0.0
    for column in range(1, sheet.max_column + 1):
        values = [sheet.value(row, column) for row in range(start_row, sheet.max_row + 1)]
        values = [value for value in values if clean_text(value)]
        if len(values) < 2:
            continue
        matches = sum(bool(predicate(value)) for value in values)
        ratio = matches / len(values)
        diversity = len({clean_text(value) for value in values}) / len(values)
        score = ratio * 0.85 + min(diversity, 1.0) * 0.15
        if matches >= 2 and score > best_score:
            best_column, best_score = column, score
    return best_column, best_score


def detect_sheet(sheet: SheetData) -> DetectedSheet:
    detected = DetectedSheet(sheet=sheet)
    best_span = 1
    max_scan_row = min(sheet.max_row, 120)
    for start in range(1, max_scan_row + 1):
        single_values = _combined_headers(sheet, start, 1)
        single_score, _single_roles = _score_headers(single_values)
        for span in (1, 2, 3):
            if span > 1 and single_score >= 6.0:
                continue
            values = _combined_headers(sheet, start, span)
            score, roles = _score_headers(values)
            adjusted = score - (span - 1) * 0.05
            if adjusted > detected.header_score:
                detected.header_score = adjusted
                detected.header_rows = list(range(start, min(start + span, sheet.max_row + 1)))
                detected.header_values = values
                detected.column_roles = roles
                best_span = span

    if detected.header_score < 2.0:
        detected.header_rows = []
        detected.header_values = {}
        detected.column_roles = {}

    for row in range(1, sheet.max_row + 1):
        values = _combined_headers(sheet, row, best_span)
        score, _roles = _score_headers(values)
        if score >= max(6.0, detected.header_score * 0.72):
            detected.repeated_header_rows.update(range(row, min(row + best_span, sheet.max_row + 1)))

    for column, role in detected.column_roles.items():
        if role == "code":
            detected.code_column = column
            detected.code_header = detected.header_values.get(column)
            detected.code_confidence = 0.99
            break

    if detected.code_column is None:
        column, score = _infer_column(sheet, detected.data_start_row, is_code_candidate)
        if column is not None and score >= 0.48:
            detected.code_column = column
            detected.code_header = detected.header_values.get(column)
            detected.code_confidence = round(min(0.89, 0.45 + score * 0.45), 3)
            detected.column_roles[column] = "code"

    if "ncm" not in detected.column_roles.values():
        column, score = _infer_column(sheet, detected.data_start_row, is_ncm)
        if column is not None and score >= 0.60 and column not in detected.column_roles:
            detected.column_roles[column] = "ncm"

    return detected
