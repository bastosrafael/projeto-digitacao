import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
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


class UploadMetadataError(Exception):
    pass


@dataclass(frozen=True)
class StoredUpload:
    file_id: str
    original_filename: str
    stored_filename: str
    size_bytes: int
    sha256: str
    uploaded_at: str


def _write_metadata(path: Path, upload: StoredUpload) -> None:
    payload = {
        "schema_version": 1,
        "file_id": upload.file_id,
        "original_filename": upload.original_filename,
        "stored_filename": upload.stored_filename,
        "size_bytes": upload.size_bytes,
        "sha256": upload.sha256,
        "uploaded_at": upload.uploaded_at,
    }
    with path.open("x", encoding="utf-8") as destination:
        path.chmod(0o600)
        json.dump(payload, destination, ensure_ascii=False, separators=(",", ":"))
        destination.write("\n")
        destination.flush()
        os.fsync(destination.fileno())


def load_upload_metadata(upload_dir: Path, file_id: str) -> StoredUpload | None:
    path = upload_dir / f"{file_id}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") != 1
            or payload.get("file_id") != file_id
            or payload.get("stored_filename") != f"{file_id}.xlsx"
        ):
            raise UploadMetadataError("Metadados de upload inconsistentes.")
        return StoredUpload(
            file_id=payload["file_id"],
            original_filename=payload["original_filename"],
            stored_filename=payload["stored_filename"],
            size_bytes=int(payload["size_bytes"]),
            sha256=payload["sha256"],
            uploaded_at=payload["uploaded_at"],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
        raise UploadMetadataError("Não foi possível ler os metadados do upload.") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sanitize_original_filename(filename: str | None) -> str:
    basename = Path((filename or "arquivo.xlsx").replace("\\", "/")).name
    sanitized = "".join(character for character in basename if character.isprintable())
    sanitized = sanitized.strip().strip(".") or "arquivo.xlsx"
    if len(sanitized) > 255:
        suffix = Path(sanitized).suffix
        sanitized = f"{Path(sanitized).stem[: 255 - len(suffix)]}{suffix}"
    return sanitized


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
    file_id = str(uuid4())
    original_filename = sanitize_original_filename(upload.filename)
    temporary_path = settings.upload_dir / f".{file_id}.part"
    temporary_metadata_path = settings.upload_dir / f".{file_id}.metadata.part"
    final_path = settings.upload_dir / f"{file_id}.xlsx"
    metadata_path = settings.upload_dir / f"{file_id}.json"
    size_bytes = 0
    digest = hashlib.sha256()

    settings.upload_dir.mkdir(parents=True, exist_ok=True, mode=0o750)

    try:
        with temporary_path.open("xb") as destination:
            temporary_path.chmod(0o600)
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_size_bytes:
                    raise UploadSizeError
                digest.update(chunk)
                destination.write(chunk)

            destination.flush()
            os.fsync(destination.fileno())

        validate_xlsx(temporary_path, original_filename)
        temporary_path.replace(final_path)
        stored = StoredUpload(
            file_id=file_id,
            original_filename=original_filename,
            stored_filename=final_path.name,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
            uploaded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        _write_metadata(temporary_metadata_path, stored)
        temporary_metadata_path.replace(metadata_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        temporary_metadata_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise

    logger.info(
        "Upload XLSX armazenado: file_id=%s size_bytes=%d",
        file_id,
        size_bytes,
    )
    return stored
