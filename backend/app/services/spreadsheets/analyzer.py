from __future__ import annotations

import time
from collections import Counter, defaultdict
from pathlib import Path

from app.services.spreadsheets.detector import DetectedSheet, detect_sheet
from app.services.spreadsheets.images import extract_images
from app.services.spreadsheets.normalization import clean_text, normalize_code
from app.services.spreadsheets.parser import SpreadsheetParseError, load_workbook
from app.services.spreadsheets.schemas import (
    AnalysisResponse,
    ImageClassification,
    Product,
    SheetSummary,
    SpreadsheetImage,
)


PRODUCT_FIELD_ROLES = {
    "item_name", "ncm", "composition", "construction", "color", "size",
    "manufacturer", "supplier", "brand", "packing_info",
}
TOTAL_MARKERS = {"total", "subtotal", "合计", "总计"}


def _is_total_row(detected: DetectedSheet, row: int) -> bool:
    values = {clean_text(value).casefold() for value in detected.sheet.row_values(row).values()}
    return bool(values & TOTAL_MARKERS)


def _role_value(detected: DetectedSheet, row: int, role: str) -> str:
    for column, column_role in detected.column_roles.items():
        if column_role == role:
            return clean_text(detected.sheet.value(row, column))
    return ""


def _has_product_data(detected: DetectedSheet, row: int) -> bool:
    populated = sum(bool(_role_value(detected, row, role)) for role in PRODUCT_FIELD_ROLES - {"packing_info"})
    return populated >= 1


def _append_unique(target: dict[str, list[str]], key: str, value: str) -> None:
    if value and value not in target.setdefault(key, []):
        target[key].append(value)


def _product_for_row(
    detected: DetectedSheet,
    row: int,
    sequence: int,
    previous_context: tuple[str, str | None, str | None] | None,
) -> tuple[Product | None, tuple[str, str | None, str | None] | None, bool]:
    if row in detected.repeated_header_rows or _is_total_row(detected, row):
        return None, previous_context, False
    raw_code = detected.sheet.value(row, detected.code_column) if detected.code_column else None
    normalized = normalize_code(raw_code) if raw_code not in (None, "") else None
    explicit = normalized is not None
    code = normalized.normalized if normalized else None
    code_original = normalized.original if normalized else None
    packing = [normalized.logistical_text] if normalized and normalized.logistical_text else []

    current_item = _role_value(detected, row, "item_name") or None
    current_ncm = _role_value(detected, row, "ncm") or None
    if code is None and previous_context and _has_product_data(detected, row):
        previous_code, previous_item, previous_ncm = previous_context
        same_documentary_block = (
            current_item is None
            or (previous_item is not None and current_item == previous_item)
            or (current_ncm is not None and previous_ncm is not None and current_ncm == previous_ncm)
        )
        if same_documentary_block:
            code = previous_code
        code_original = None
    if code is None and not _has_product_data(detected, row):
        return None, previous_context, False

    product_id = code or f"ROW-{sequence:05d}"
    original_values: dict[str, list[str]] = {}
    for column, role in detected.column_roles.items():
        value = clean_text(detected.sheet.value(row, column))
        if value:
            _append_unique(original_values, role, value)
    if code_original:
        _append_unique(original_values, "code", code_original)

    values = {role: _role_value(detected, row, role) or None for role in PRODUCT_FIELD_ROLES}
    product = Product(
        product_id=product_id,
        code=code,
        code_original=code_original,
        code_confidence=detected.code_confidence if code else 0.0,
        sheet_name=detected.sheet.name,
        row_numbers=[row],
        item_name=values["item_name"],
        ncm=values["ncm"],
        composition=values["composition"],
        construction=values["construction"],
        color=values["color"],
        size=values["size"],
        manufacturer=values["manufacturer"],
        supplier=values["supplier"],
        brand=values["brand"],
        packing_info=packing + ([values["packing_info"]] if values["packing_info"] else []),
        original_values=original_values,
        status="OK" if code else "REVISAR",
        warnings=[] if code else ["Código não identificado"],
    )
    if code:
        prior_item = previous_context[1] if previous_context and previous_context[0] == code else None
        prior_ncm = previous_context[2] if previous_context and previous_context[0] == code else None
        context = (code, current_item or prior_item, current_ncm or prior_ncm)
    else:
        context = None
    return product, context, explicit


def _merge_product(target: Product, source: Product) -> None:
    for row in source.row_numbers:
        if row not in target.row_numbers:
            target.row_numbers.append(row)
    for field in ("item_name", "ncm", "composition", "construction", "color", "size", "manufacturer", "supplier", "brand"):
        if getattr(target, field) is None and getattr(source, field) is not None:
            setattr(target, field, getattr(source, field))
    for value in source.packing_info:
        if value and value not in target.packing_info:
            target.packing_info.append(value)
    for role, values in source.original_values.items():
        for value in values:
            _append_unique(target.original_values, role, value)
    if target.code_original is None and source.code_original:
        target.code_original = source.code_original


def _attach_image(product: Product, image: SpreadsheetImage) -> None:
    image.related_code = product.code
    mapping = {
        ImageClassification.PRODUCT_IMAGE: product.images.product,
        ImageClassification.LABEL_IMAGE: product.images.labels,
        ImageClassification.WASH_LABEL: product.images.wash_labels,
        ImageClassification.HANGTAG: product.images.hangtags,
        ImageClassification.OTHER: product.images.other,
    }
    mapping[image.classification].append(image)


def analyze_workbook(path: Path, file_id: str) -> AnalysisResponse:
    started = time.perf_counter()
    warnings: list[str] = []
    with load_workbook(path) as workbook:
        detected_sheets = [detect_sheet(sheet) for sheet in workbook.sheets]
        images = extract_images(workbook, detected_sheets)
        image_counts = Counter(image.sheet for image in images)
        relevant = [sheet for sheet in detected_sheets if sheet.header_rows and sheet.header_score >= 2.0]
        if not relevant:
            raise SpreadsheetParseError("Nenhuma tabela reconhecível foi identificada.")

        main = max(
            relevant,
            key=lambda item: item.header_score + min(item.sheet.max_row, 1000) / 50 + image_counts[item.sheet.name] / 10,
        )
        products_by_key: dict[str, Product] = {}
        row_products: dict[tuple[str, int], Product] = {}
        explicit_code_rows = 0
        review_sequence = 1

        for detected in relevant:
            previous_context = None
            for row in range(detected.data_start_row, detected.sheet.max_row + 1):
                product, previous_context, explicit = _product_for_row(
                    detected, row, review_sequence, previous_context
                )
                if product is None:
                    continue
                if product.code is None:
                    review_sequence += 1
                if explicit:
                    explicit_code_rows += 1
                key = product.code or f"{detected.sheet.name}:{product.product_id}"
                if key in products_by_key:
                    _merge_product(products_by_key[key], product)
                else:
                    products_by_key[key] = product
                row_products[(detected.sheet.name, row)] = products_by_key[key]

        for image in images:
            candidates = [
                (abs(row - image.anchor_row), 0 if row <= image.anchor_row else 1, product)
                for (sheet_name, row), product in row_products.items()
                if sheet_name == image.sheet and abs(row - image.anchor_row) <= 8
            ]
            if candidates:
                _, _, product = min(candidates, key=lambda item: (item[0], item[1]))
                _attach_image(product, image)
                continue
            key = f"{image.sheet}:IMAGE:{image.anchor_row}"
            if key not in products_by_key:
                product = Product(
                    product_id=f"ROW-{review_sequence:05d}",
                    code_confidence=0.0,
                    sheet_name=image.sheet,
                    row_numbers=[image.anchor_row],
                    status="REVISAR",
                    warnings=["Código não identificado", "Imagem sem linha de produto associada"],
                )
                review_sequence += 1
                products_by_key[key] = product
            _attach_image(products_by_key[key], image)

        products = sorted(products_by_key.values(), key=lambda product: (product.sheet_name, min(product.row_numbers)))
        repeated_codes = {
            product.code: product.row_numbers
            for product in products
            if product.code and len(product.row_numbers) > 1
        }
        classification_counts = Counter(image.classification for image in images)
        unassociated = sum(image.related_code is None for image in images)
        if unassociated:
            warnings.append(f"{unassociated} imagem(ns) sem código relacionado; produtos marcados para revisão.")

        summaries = []
        for detected in detected_sheets:
            summaries.append(
                SheetSummary(
                    name=detected.sheet.name,
                    rows=detected.sheet.max_row,
                    columns=detected.sheet.max_column,
                    header_rows=detected.header_rows,
                    repeated_header_rows=sorted(detected.repeated_header_rows),
                    header_values={str(column): value for column, value in detected.header_values.items()},
                    merged_ranges=len(detected.sheet.merges),
                    code_column=detected.code_column,
                    code_header=detected.code_header,
                    code_confidence=detected.code_confidence,
                    images_detected=image_counts[detected.sheet.name],
                    relevant=detected in relevant,
                )
            )

        auxiliary_fields = sorted(
            {
                role
                for detected in relevant
                for role in detected.column_roles.values()
                if role not in {"code", "image"}
            }
        )
        unique_media = len({image.sha256 for image in images})
        duration_ms = round((time.perf_counter() - started) * 1000)
        return AnalysisResponse(
            file_id=file_id,
            main_sheet=main.sheet.name,
            sheets=len(workbook.sheets),
            rows=main.sheet.max_row,
            columns=main.sheet.max_column,
            header_rows=main.header_rows,
            code_column=main.code_column,
            code_header=main.code_header,
            code_confidence=main.code_confidence,
            images_detected=len(images),
            unique_media=unique_media,
            product_images=classification_counts[ImageClassification.PRODUCT_IMAGE],
            label_images=classification_counts[ImageClassification.LABEL_IMAGE],
            wash_labels=classification_counts[ImageClassification.WASH_LABEL],
            hangtags=classification_counts[ImageClassification.HANGTAG],
            other_images=classification_counts[ImageClassification.OTHER],
            codes_detected=explicit_code_rows,
            unique_products=sum(product.code is not None for product in products),
            repeated_codes=repeated_codes,
            auxiliary_fields=auxiliary_fields,
            duration_ms=duration_ms,
            warnings=warnings,
            sheet_summaries=summaries,
            products=products,
        )
