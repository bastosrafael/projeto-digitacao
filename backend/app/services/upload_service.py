import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile, is_zipfile

from fastapi import UploadFile

from app.config import Settings

logger = logging.getLogger(__name__)

UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_REQUIRED_XML_SIZE = 2 * 1024 * 1024
REQUIRED_XLSX_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
}
WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
OFFICE_DOCUMENT_RELATIONSHIP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)


class UploadValidationError(Exception):
    pass


class UploadSizeError(Exception):
    pass


@dataclass(frozen=True)
class StoredUpload:
    upload_id: str
    original_filename: str
    stored_filename: str
    size_bytes: int


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_required_xml(archive: ZipFile, name: str) -> ElementTree.Element:
    info = archive.getinfo(name)
    if info.file_size > MAX_REQUIRED_XML_SIZE:
        raise UploadValidationError("Estrutura XLSX inválida.")

    with archive.open(info) as item:
        data = item.read(MAX_REQUIRED_XML_SIZE + 1)
    if len(data) > MAX_REQUIRED_XML_SIZE:
        raise UploadValidationError("Estrutura XLSX inválida.")

    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise UploadValidationError("Estrutura XLSX inválida.") from exc


def validate_xlsx(path: Path, original_filename: str) -> None:
    if Path(original_filename).suffix.lower() != ".xlsx":
        raise UploadValidationError("Envie um arquivo com extensão .xlsx.")

    if not is_zipfile(path):
        raise UploadValidationError("O arquivo enviado não é um XLSX válido.")

    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if not REQUIRED_XLSX_PARTS.issubset(names):
                raise UploadValidationError("Estrutura XLSX incompleta ou inválida.")

            content_types = _read_required_xml(archive, "[Content_Types].xml")
            relationships = _read_required_xml(archive, "_rels/.rels")
            workbook = _read_required_xml(archive, "xl/workbook.xml")

            if _local_name(content_types.tag) != "Types":
                raise UploadValidationError("Estrutura XLSX inválida.")
            if _local_name(relationships.tag) != "Relationships":
                raise UploadValidationError("Estrutura XLSX inválida.")
            if _local_name(workbook.tag) != "workbook":
                raise UploadValidationError("Estrutura XLSX inválida.")

            has_workbook_content_type = any(
                _local_name(item.tag) == "Override"
                and item.attrib.get("PartName") == "/xl/workbook.xml"
                and item.attrib.get("ContentType") == WORKBOOK_CONTENT_TYPE
                for item in content_types
            )
            has_workbook_relationship = any(
                _local_name(item.tag) == "Relationship"
                and item.attrib.get("Type") == OFFICE_DOCUMENT_RELATIONSHIP
                and item.attrib.get("Target", "").lstrip("/") == "xl/workbook.xml"
                for item in relationships
            )
            if not has_workbook_content_type or not has_workbook_relationship:
                raise UploadValidationError("Estrutura XLSX incompleta ou inválida.")
    except (BadZipFile, KeyError, RuntimeError, OSError) as exc:
        raise UploadValidationError("O arquivo enviado não é um XLSX válido.") from exc


async def store_upload(upload: UploadFile, settings: Settings) -> StoredUpload:
    upload_id = str(uuid4())
    original_filename = Path(upload.filename or "arquivo.xlsx").name
    temporary_path = settings.upload_dir / f".{upload_id}.part"
    final_path = settings.upload_dir / f"{upload_id}.xlsx"
    size_bytes = 0

    settings.upload_dir.mkdir(parents=True, exist_ok=True, mode=0o750)

    try:
        with temporary_path.open("xb") as destination:
            temporary_path.chmod(0o600)
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_size_bytes:
                    raise UploadSizeError
                destination.write(chunk)

            destination.flush()
            os.fsync(destination.fileno())

        validate_xlsx(temporary_path, original_filename)
        temporary_path.replace(final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise

    logger.info(
        "Upload XLSX armazenado: upload_id=%s size_bytes=%d",
        upload_id,
        size_bytes,
    )
    return StoredUpload(
        upload_id=upload_id,
        original_filename=original_filename,
        stored_filename=final_path.name,
        size_bytes=size_bytes,
    )
