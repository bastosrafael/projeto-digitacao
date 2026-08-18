"""Endpoint de geração de descrição técnica DUIMP — Fase 8A/8B."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.duimp_description import DuimpDescriptionService
from app.services.research.duimp_schemas import DuimpDescriptionResult, DuimpGenerateRequest
from app.services.research.labels_multimodal import LabelsMultimodalService
from app.services.spreadsheets import analyze_workbook

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
            data = json.loads(f.read_text())
            payload = data.get("payload", {})
            return payload
        except Exception:
            continue
    return None


def _build_packing_fallback(
    settings: Settings,
    file_id: str,
    product_id: str,
) -> dict | None:
    """Constrói labels_result parcial a partir da packing list quando labels_multimodal não existe."""
    xlsx_path = settings.upload_dir / f"{file_id}.xlsx"
    if not xlsx_path.exists():
        return None

    try:
        analysis = analyze_workbook(xlsx_path, file_id)
    except Exception:
        logger.exception("packing_fallback_analyze_error file_id=%s", file_id)
        return None

    product = None
    for p in analysis.products:
        if p.code and (p.code == product_id or p.product_id == product_id):
            product = p
            break

    if product is None:
        return None

    confirmed_fields = []
    unknown_fields = []

    field_map = {
        "code": product.code,
        "item_name": product.item_name,
        "ncm": product.ncm,
        "composition": product.composition,
        "construction": product.construction,
        "manufacturer": product.manufacturer,
        "supplier": product.supplier,
        "brand": product.brand,
        "color": product.color,
        "size": product.size,
    }

    for field, value in field_map.items():
        if value:
            confirmed_fields.append({
                "field": field,
                "value": value,
                "evidence_ids": ["PACKING-001"],
                "source_types": ["packing_list"],
            })
        else:
            unknown_fields.append(field)

    if not confirmed_fields:
        return None

    return {
        "code": product.code,
        "product_id": product.product_id,
        "decision": "REVIEW",
        "confidence": "LOW",
        "internal_support": "WEAK",
        "external_support": "NONE",
        "product_image_used": False,
        "wash_label_used": False,
        "hangtag_used": False,
        "evidence_used": ["PACKING-001"],
        "confirmed_fields": confirmed_fields,
        "conflicts": [],
        "unknown_fields": unknown_fields,
        "warnings": ["Packing list fallback — no multimodal cross-analysis."],
        "packing_fallback": True,
    }


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
            data = json.loads(f.read_text())
            payload = data.get("payload", {})
            code = payload.get("code") or payload.get("product_id", "")
            if code == product_id:
                labels_result = payload
                break
        except Exception:
            continue

    packing_fallback = False
    if labels_result is None:
        labels_result = _build_packing_fallback(settings, file_id, product_id)
        if labels_result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No evidence found for product '{product_id}'. "
                       "Run /research/multimodal/labels first or ensure the product "
                       "exists in the uploaded spreadsheet.",
            )
        packing_fallback = True
        logger.info(
            "duimp_packing_fallback code=%s confirmed_fields=%s",
            product_id,
            len(labels_result.get("confirmed_fields", [])),
        )

    # Read wash evidence from cache (any entry — wash is per-image, take first OK)
    wash_evidence = None
    w_cache = _wash_cache(settings)
    if w_cache.directory.exists():
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
            packing_fallback=packing_fallback,
        )
        return result
    except OmniRouteError as exc:
        logger.error("duimp_generation_omniroute_error code=%s error=%s", product_id, exc)
        raise HTTPException(
            status_code=503,
            detail="LLM service temporarily unavailable for description generation.",
        )
