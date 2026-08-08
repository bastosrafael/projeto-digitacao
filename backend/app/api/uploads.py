from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.upload_service import UploadSizeError, UploadValidationError, store_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadConfigResponse(BaseModel):
    max_upload_size_mb: int
    accepted_extensions: list[str]


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    stored_filename: str
    size_bytes: int
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
        status="uploaded",
    )
