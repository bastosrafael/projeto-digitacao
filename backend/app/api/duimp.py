"""Endpoint de geração de descrição técnica DUIMP — Fase 8A."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.duimp_description import DuimpDescriptionService
from app.services.research.duimp_schemas import DuimpDescriptionResult, DuimpGenerateRequest
from app.services.research.labels_multimodal import LabelsMultimodalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["duimp"])


def _labels_multimodal_cache(settings: Settings) -> AnalysisCache:
    return AnalysisCache(
        settings.labels_multimodal_cache_dir,
        settings.labels_multimodal_cache_ttl_seconds,
    )


def _wash_cache(settings: Settings) -> AnalysisCache:
    return AnalysisCache(
        settings.wash_label_cache_dir,
        settings.wash_label_cache_ttl_seconds,
    )


def _hangtag_cache(settings: Settings) -> AnalysisCache:
    return AnalysisCache(
        settings.hangtag_cache_dir,
        settings.hangtag_cache_ttl_seconds,
    )


def _visual_cache(settings: Settings) -> AnalysisCache:
    return AnalysisCache(
        settings.visual_analysis_cache_dir,
        settings.visual_analysis_cache_ttl_seconds,
    )


def _find_cached_result(cache: AnalysisCache, prefix_filter: str | None = None) -> dict | None:
    """Read the first (or matching) cached payload from a cache directory."""
    cache_dir = cache.cache_dir
    if not cache_dir.exists():
        return None
    for f in sorted(cache_dir.glob("*.json")):
        try:
            import json
            data = json.loads(f.read_text())
            payload = data.get("payload", {})
            return payload
        except Exception:
            continue
    return None


@router.post("/{file_id}/duimp/generate", response_model=DuimpDescriptionResult)
async def generate_description(
    request: DuimpGenerateRequest,
    file_id: str,
    settings: Settings = Depends(get_settings),
) -> DuimpDescriptionResult:
    """Gera descrição técnica DUIMP para 1 produto usando evidências em cache."""
    product_id = request.product_id

    # Read labels multimodal result from cache
    lm_cache = _labels_multimodal_cache(settings)
    labels_result = None
    for f in sorted(lm_cache.directory.glob("*.json")):
        try:
            import json
            data = json.loads(f.read_text())
            payload = data.get("payload", {})
            code = payload.get("code") or payload.get("product_id", "")
            if code == product_id:
                labels_result = payload
                break
        except Exception:
            continue

    if labels_result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No labels multimodal evidence found for product '{product_id}'. "
                   "Run /research/multimodal/labels first.",
        )

    # Read wash evidence from cache (any entry — wash is per-image, take first OK)
    wash_evidence = None
    w_cache = _wash_cache(settings)
    if w_cache.directory.exists():
        import json
        for f in sorted(w_cache.directory.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                payload = data.get("payload", {})
                if payload.get("status") == "OK" and payload.get("product_code") == product_id:
                    wash_evidence = payload
                    break
            except Exception:
                continue

    # Read hangtag evidence from cache
    hangtag_evidence = None
    h_cache = _hangtag_cache(settings)
    if h_cache.directory.exists():
        import json
        for f in sorted(h_cache.directory.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                payload = data.get("payload", {})
                if payload.get("status") == "OK" and payload.get("product_code") == product_id:
                    hangtag_evidence = payload
                    break
            except Exception:
                continue

    # Read visual evidence from cache
    visual_evidence = None
    v_cache = _visual_cache(settings)
    if v_cache.directory.exists():
        import json
        for f in sorted(v_cache.directory.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                payload = data.get("payload", {})
                if payload.get("product_code") == product_id and payload.get("image_type") == "PRODUCT_IMAGE":
                    visual_evidence = payload
                    break
            except Exception:
                continue

    # Generate description
    gateway = OmniRouteService(settings)
    service = DuimpDescriptionService(settings, gateway)

    try:
        result = await service.generate(
            labels_result,
            wash_evidence=wash_evidence,
            hangtag_evidence=hangtag_evidence,
            visual_evidence=visual_evidence,
        )
        return result
    except OmniRouteError as exc:
        logger.error("duimp_generation_omniroute_error code=%s error=%s", product_id, exc)
        raise HTTPException(
            status_code=503,
            detail="LLM service temporarily unavailable for description generation.",
        )
