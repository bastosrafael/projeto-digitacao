import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services.omniroute import OmniRouteService
from app.services import upload_service
from app.services.upload_service import sanitize_original_filename

client = TestClient(app)

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>
"""
RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
WORKBOOK = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheets/>
</workbook>
"""


def make_xlsx(extra_size: int = 0) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("xl/workbook.xml", WORKBOOK)
        if extra_size:
            archive.writestr("xl/media/padding.bin", b"x" * extra_size)
    return buffer.getvalue()


def make_xlsx_with_exact_size(target_size: int) -> bytes:
    one_byte_file = make_xlsx(1)
    archive_overhead = len(one_byte_file) - 1
    data = make_xlsx(target_size - archive_overhead)
    assert len(data) == target_size
    return data


@pytest.fixture
def upload_settings(tmp_path: Path):
    settings = Settings(
        max_upload_size_mb=1,
        upload_dir=tmp_path,
        cors_allowed_origins="https://projeto-digitacao.netlify.app",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.clear()


def test_upload_config_exposes_configured_limit(upload_settings: Settings) -> None:
    response = client.get("/api/uploads/config")

    assert response.status_code == 200
    assert response.json() == {
        "max_upload_size_mb": 1,
        "accepted_extensions": [".xlsx"],
    }


def test_upload_accepts_valid_xlsx_and_uses_uuid_name(upload_settings: Settings) -> None:
    data = make_xlsx()

    response = client.post(
        "/api/uploads",
        files={
            "file": (
                "IM0416-26 - PACKING LIST.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "IM0416-26 - PACKING LIST.xlsx"
    assert payload["size_bytes"] == len(data)
    assert payload["status"] == "uploaded"
    assert payload["stored_filename"] == f'{payload["file_id"]}.xlsx'
    assert payload["sha256"] == hashlib.sha256(data).hexdigest()
    assert payload["uploaded_at"].endswith("Z")
    assert (upload_settings.upload_dir / payload["stored_filename"]).read_bytes() == data
    metadata_path = upload_settings.upload_dir / f'{payload["file_id"]}.json'
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata == {
        "schema_version": 1,
        "file_id": payload["file_id"],
        "original_filename": "IM0416-26 - PACKING LIST.xlsx",
        "stored_filename": payload["stored_filename"],
        "size_bytes": len(data),
        "sha256": payload["sha256"],
        "uploaded_at": payload["uploaded_at"],
    }
    assert oct(metadata_path.stat().st_mode & 0o777) == "0o600"
    assert not list(upload_settings.upload_dir.glob("*.part"))


def test_upload_metadata_can_be_retrieved_by_controlled_id(upload_settings: Settings) -> None:
    created = client.post(
        "/api/uploads",
        files={"file": ("produtos.xlsx", make_xlsx(), "application/octet-stream")},
    ).json()

    response = client.get(f'/api/uploads/{created["file_id"]}')

    assert response.status_code == 200
    assert response.json() == created
    assert client.get("/api/uploads/not-a-uuid").status_code == 422
    assert client.get(f"/api/uploads/{'0' * 36}").status_code == 422


def test_metadata_failure_removes_xlsx_and_partial_files(
    upload_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_metadata(*_args: object) -> None:
        raise OSError("falha simulada")

    monkeypatch.setattr(upload_service, "_write_metadata", fail_metadata)

    response = client.post(
        "/api/uploads",
        files={"file": ("produtos.xlsx", make_xlsx(), "application/octet-stream")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Não foi possível armazenar o arquivo."}
    assert list(upload_settings.upload_dir.iterdir()) == []


def test_upload_never_calls_omniroute(
    upload_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden_chat(self: OmniRouteService, message: str) -> str:
        raise AssertionError("O upload não deve chamar o OmniRoute")

    monkeypatch.setattr(OmniRouteService, "chat", forbidden_chat)

    response = client.post(
        "/api/uploads",
        files={"file": ("produtos.xlsx", make_xlsx(), "application/octet-stream")},
    )

    assert response.status_code == 201


def test_upload_accepts_file_exactly_at_limit(upload_settings: Settings) -> None:
    data = make_xlsx_with_exact_size(1024 * 1024)

    response = client.post(
        "/api/uploads",
        files={"file": ("limite.xlsx", data, "application/octet-stream")},
    )

    assert response.status_code == 201
    assert response.json()["size_bytes"] == 1024 * 1024


def test_original_filename_is_metadata_sanitized() -> None:
    assert sanitize_original_filename("../../pasta\\produtos\x00.xlsx") == "produtos.xlsx"
    assert sanitize_original_filename(".xlsx") == "xlsx"


def test_upload_rejects_file_over_limit_and_removes_partial(upload_settings: Settings) -> None:
    response = client.post(
        "/api/uploads",
        files={"file": ("grande.xlsx", make_xlsx(1024 * 1024), "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Arquivo excede o limite permitido de 1 MB."
    }
    assert list(upload_settings.upload_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("filename", "content", "expected_detail"),
    [
        ("arquivo.xls", make_xlsx(), "Envie um arquivo com extensão .xlsx."),
        ("arquivo.xlsx", "não é zip".encode(), "O arquivo enviado não é um XLSX válido."),
    ],
)
def test_upload_rejects_invalid_xlsx_and_removes_file(
    upload_settings: Settings,
    filename: str,
    content: bytes,
    expected_detail: str,
) -> None:
    response = client.post(
        "/api/uploads",
        files={"file": (filename, content, "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": expected_detail}
    assert list(upload_settings.upload_dir.iterdir()) == []


def test_cors_allows_only_configured_netlify_origin() -> None:
    response = client.options(
        "/api/uploads",
        headers={
            "Origin": "https://projeto-digitacao.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://projeto-digitacao.netlify.app"
    )
