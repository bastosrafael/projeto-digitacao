from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.services.upload_service import (
    UploadMetadataError,
    UploadSizeError,
    UploadValidationError,
    load_upload_metadata,
    store_upload,
)
from app.services.spreadsheets import analyze_workbook
from app.services.spreadsheets.parser import SpreadsheetParseError
from app.services.spreadsheets.schemas import AnalysisResponse

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadConfigResponse(BaseModel):
    max_upload_size_mb: int
    accepted_extensions: list[str]


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    stored_filename: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    status: str


@router.get("/config", response_model=UploadConfigResponse)
async def upload_config(settings: Settings = Depends(get_settings)) -> UploadConfigResponse:
    return UploadConfigResponse(
        max_upload_size_mb=settings.max_upload_size_mb,
        accepted_extensions=[".xlsx"],
    )


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_spreadsheet(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    try:
        stored = await store_upload(file, settings)
    except UploadSizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede o limite permitido de {settings.max_upload_size_mb} MB.",
        ) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível armazenar o arquivo.",
        ) from exc
    finally:
        await file.close()

    return UploadResponse(
        file_id=stored.file_id,
        filename=stored.original_filename,
        stored_filename=stored.stored_filename,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        uploaded_at=stored.uploaded_at,
        status="uploaded",
    )


@router.get("/{file_id}", response_model=UploadResponse)
async def upload_metadata(
    file_id: UUID,
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    controlled_file_id = str(file_id)
    try:
        stored = load_upload_metadata(settings.upload_dir, controlled_file_id)
    except UploadMetadataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível consultar os metadados do upload.",
        ) from exc
    if stored is None or not (settings.upload_dir / stored.stored_filename).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload não encontrado.")
    return UploadResponse(
        file_id=stored.file_id,
        filename=stored.original_filename,
        stored_filename=stored.stored_filename,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        uploaded_at=stored.uploaded_at,
        status="uploaded",
    )


@router.post("/{file_id}/analyze", response_model=AnalysisResponse)
async def analyze_spreadsheet(
    file_id: UUID,
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    controlled_file_id = str(file_id)
    path = settings.upload_dir / f"{controlled_file_id}.xlsx"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload não encontrado.")
    try:
        return await run_in_threadpool(analyze_workbook, path, controlled_file_id)
    except SpreadsheetParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
