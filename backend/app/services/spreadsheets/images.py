from __future__ import annotations

import hashlib
import io
import posixpath
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

from app.services.spreadsheets.detector import DetectedSheet
from app.services.spreadsheets.parser import (
    PACKAGE_REL_NS,
    REL_NS,
    SpreadsheetParseError,
    WorkbookData,
    load_workbook,
    resolve_target,
)
from app.services.spreadsheets.schemas import ImageClassification, SpreadsheetImage


DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_MAIN_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"xdr": DRAWING_NS, "a": DRAWING_MAIN_NS, "r": REL_NS}


@dataclass(frozen=True)
class MediaDetails:
    sha256: str
    width: int | None
    height: int | None


@dataclass(frozen=True)
class ExtractedProductImage:
    image_id: str
    image_type: str
    product_code: str
    sheet: str
    anchor_row: int
    anchor_column: int
    media_reference: str
    data: bytes
    sha256: str
    mime_type: str
    width: int
    height: int


class ProductImageError(ValueError):
    pass


def _relations(workbook: WorkbookData, path: str) -> dict[str, str]:
    rels_path = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
    if rels_path not in workbook.archive.namelist():
        return {}
    root = ElementTree.fromstring(workbook.archive.read(rels_path))
    return {
        item.attrib["Id"]: item.attrib["Target"]
        for item in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        if item.attrib.get("Type", "").endswith("/image")
    }


def _media_details(workbook: WorkbookData, reference: str, cache: dict[str, MediaDetails]) -> MediaDetails:
    if reference in cache:
        return cache[reference]
    data = workbook.archive.read(reference)
    width = height = None
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
    except (OSError, ValueError):
        pass
    details = MediaDetails(hashlib.sha256(data).hexdigest(), width, height)
    cache[reference] = details
    return details


def classify_image(column_role: str | None) -> ImageClassification:
    return {
        "image": ImageClassification.PRODUCT_IMAGE,
        "wash_label": ImageClassification.WASH_LABEL,
        "hangtag": ImageClassification.HANGTAG,
        "label": ImageClassification.LABEL_IMAGE,
    }.get(column_role, ImageClassification.OTHER)


def extract_images(workbook: WorkbookData, sheets: list[DetectedSheet]) -> list[SpreadsheetImage]:
    images: list[SpreadsheetImage] = []
    cache: dict[str, MediaDetails] = {}
    for detected in sheets:
        for drawing_path in detected.sheet.drawing_paths:
            root = ElementTree.fromstring(workbook.archive.read(drawing_path))
            relations = _relations(workbook, drawing_path)
            anchors = list(root.findall("xdr:oneCellAnchor", NS)) + list(root.findall("xdr:twoCellAnchor", NS))
            for anchor in anchors:
                start = anchor.find("xdr:from", NS)
                blip = anchor.find(".//a:blip", NS)
                if start is None or blip is None:
                    continue
                relation_id = blip.attrib.get(f"{{{REL_NS}}}embed")
                if not relation_id or relation_id not in relations:
                    continue
                row_node = start.find("xdr:row", NS)
                column_node = start.find("xdr:col", NS)
                if row_node is None or column_node is None:
                    continue
                row = int(row_node.text or "0") + 1
                column = int(column_node.text or "0") + 1
                media_reference = resolve_target(drawing_path, relations[relation_id])
                details = _media_details(workbook, media_reference, cache)
                classification = classify_image(detected.column_roles.get(column))
                index = len(images) + 1
                images.append(
                    SpreadsheetImage(
                        image_id=f"IMG-{index:05d}",
                        sheet=detected.sheet.name,
                        anchor_row=row,
                        anchor_column=column,
                        width=details.width,
                        height=details.height,
                        media_reference=media_reference,
                        sha256=details.sha256,
                        classification=classification,
                    )
                )
    return images


def extract_product_image_bytes(
    path: Path,
    product_code: str,
    image: SpreadsheetImage,
) -> ExtractedProductImage:
    """Recupera uma mídia já associada pelo parser, sem expor o ZIP fora desta abstração."""
    if image.classification is not ImageClassification.PRODUCT_IMAGE:
        raise ProductImageError("A imagem selecionada não é PRODUCT_IMAGE.")
    if image.related_code != product_code:
        raise ProductImageError("A imagem não está associada ao código solicitado.")
    try:
        with load_workbook(path) as workbook:
            data = workbook.archive.read(image.media_reference)
    except (KeyError, OSError, SpreadsheetParseError) as exc:
        raise ProductImageError("Não foi possível recuperar a imagem associada.") from exc

    digest = hashlib.sha256(data).hexdigest()
    if digest != image.sha256:
        raise ProductImageError("O hash da imagem recuperada diverge da associação analisada.")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image_format = (opened.format or "").upper()
            width, height = opened.size
    except (OSError, ValueError) as exc:
        raise ProductImageError("A mídia associada não é uma imagem válida.") from exc
    mime = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image_format)
    if mime is None:
        raise ProductImageError("Somente imagens JPEG e PNG são aceitas.")
    return ExtractedProductImage(
        image_id=image.image_id,
        image_type=image.classification.value,
        product_code=product_code,
        sheet=image.sheet,
        anchor_row=image.anchor_row,
        anchor_column=image.anchor_column,
        media_reference=image.media_reference,
        data=data,
        sha256=digest,
        mime_type=mime,
        width=width,
        height=height,
    )
