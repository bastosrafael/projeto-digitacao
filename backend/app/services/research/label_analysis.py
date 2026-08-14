from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.label_schemas import (
    Confidence,
    FiberComposition,
    HangtagEvidence,
    LabeledField,
    LlmHangtagAttributes,
    LlmWashLabelAttributes,
    WashLabelEvidence,
)
from app.services.research.visual_analysis import VisualAnalysisError, prepare_image
from app.services.spreadsheets.images import ExtractedProductImage

logger = logging.getLogger(__name__)

WASH_PROMPT_VERSION = "wash-label-extraction-v1"
WASH_ANALYSIS_VERSION = "wash-label-analysis-v1"
HANGTAG_PROMPT_VERSION = "hangtag-extraction-v1"
HANGTAG_ANALYSIS_VERSION = "hangtag-analysis-v1"
PREPROCESSING_VERSION = "visual-image-normalization-v1"

_LABEL_SEMAPHORE = asyncio.Semaphore(1)


class LabelAnalysisError(ValueError):
    pass


def _load_prompt(name: str) -> str:
    from importlib.resources import files
    return files("app.prompts").joinpath(name).read_text(encoding="utf-8")


def _wash_prompt() -> str:
    return _load_prompt("wash_label_extraction_v1.txt")


def _hangtag_prompt() -> str:
    return _load_prompt("hangtag_extraction_v1.txt")


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise LabelAnalysisError("a resposta de label não é um objeto JSON")
    return value


def _validate_composition_sum(composition: list[FiberComposition]) -> tuple[int | None, bool | None]:
    percentages = [item.percentage for item in composition if item.percentage is not None]
    if not percentages:
        return None, None
    total = sum(percentages)
    return total, total == 100


def _calibrate_wash(attributes: LlmWashLabelAttributes) -> LlmWashLabelAttributes:
    if not attributes.readable:
        return attributes
    total, valid = _validate_composition_sum(attributes.composition)
    warnings = list(attributes.warnings)
    if total is not None and not valid:
        warnings.append("composition_percentage_sum_invalid")
    unknown = list(dict.fromkeys(attributes.unknown_fields))
    for field_name in ("size", "country_of_origin", "brand", "style_code"):
        field_value = getattr(attributes, field_name)
        if isinstance(field_value, LabeledField) and field_value.value.casefold() == "unknown" and field_name not in unknown:
            unknown.append(field_name)
    return attributes.model_copy(update={
        "unknown_fields": unknown[:30],
        "warnings": list(dict.fromkeys(warnings))[:20],
    })


def _calibrate_hangtag(attributes: LlmHangtagAttributes) -> LlmHangtagAttributes:
    if not attributes.readable:
        return attributes
    total, valid = _validate_composition_sum(attributes.composition)
    warnings = list(attributes.warnings)
    if total is not None and not valid:
        warnings.append("composition_percentage_sum_invalid")
    unknown = list(dict.fromkeys(attributes.unknown_fields))
    for field_name in ("brand", "style_code", "model", "size", "declared_color", "sku", "reference", "visible_barcode_text", "material", "country"):
        field_value = getattr(attributes, field_name)
        if isinstance(field_value, LabeledField) and field_value.value.casefold() == "unknown" and field_name not in unknown:
            unknown.append(field_name)
    return attributes.model_copy(update={
        "unknown_fields": unknown[:30],
        "warnings": list(dict.fromkeys(warnings))[:20],
    })


class LabelAnalysisService:
    def __init__(
        self,
        settings: Settings,
        gateway: OmniRouteService | None = None,
        wash_cache: AnalysisCache | None = None,
        hangtag_cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.wash_cache = wash_cache or AnalysisCache(
            settings.wash_label_cache_dir, settings.wash_label_cache_ttl_seconds
        )
        self.hangtag_cache = hangtag_cache or AnalysisCache(
            settings.hangtag_cache_dir, settings.hangtag_cache_ttl_seconds
        )

    def _cache_for(self, image_type: str) -> AnalysisCache:
        if image_type == "WASH_LABEL":
            return self.wash_cache
        return self.hangtag_cache

    def _prompt_for(self, image_type: str) -> str:
        if image_type == "WASH_LABEL":
            return _wash_prompt()
        return _hangtag_prompt()

    def _prompt_version(self, image_type: str) -> str:
        return WASH_PROMPT_VERSION if image_type == "WASH_LABEL" else HANGTAG_PROMPT_VERSION

    def _analysis_version(self, image_type: str) -> str:
        return WASH_ANALYSIS_VERSION if image_type == "WASH_LABEL" else HANGTAG_ANALYSIS_VERSION

    async def analyze_wash_label(
        self,
        file_id: str,
        image: ExtractedProductImage,
        *,
        refresh_cache: bool,
    ) -> tuple[WashLabelEvidence, int, int, int]:
        evidence, calls, hits, misses = await self._analyze_label(file_id, image, refresh_cache=refresh_cache)
        return evidence, calls, hits, misses

    async def analyze_hangtag(
        self,
        file_id: str,
        image: ExtractedProductImage,
        *,
        refresh_cache: bool,
    ) -> tuple[HangtagEvidence, int, int, int]:
        evidence, calls, hits, misses = await self._analyze_label(file_id, image, refresh_cache=refresh_cache)
        return evidence, calls, hits, misses

    async def _analyze_label(
        self,
        file_id: str,
        image: ExtractedProductImage,
        *,
        refresh_cache: bool,
    ) -> tuple[WashLabelEvidence | HangtagEvidence, int, int, int]:
        prepared = prepare_image(
            image,
            max_bytes=self.settings.visual_image_max_bytes,
            max_side=self.settings.visual_image_max_side,
        )
        prompt_version = self._prompt_version(image.image_type)
        analysis_version = self._analysis_version(image.image_type)
        identity = {
            "analysis_version": analysis_version,
            "image_hash": prepared.sha256,
            "product_code": image.product_code,
            "prompt_version": prompt_version,
            "vision_model": self.settings.omniroute_vision_model,
            "image_type": image.image_type,
            "preprocessing_version": PREPROCESSING_VERSION,
        }
        cache = self._cache_for(image.image_type)
        cache_key = cache.key(identity)
        data_url = f"data:{prepared.mime_type};base64,{base64.b64encode(prepared.data).decode('ascii')}"
        user_text = json.dumps({
            "image_id": image.image_id,
            "image_type": image.image_type,
            "product_code": image.product_code,
        }, ensure_ascii=False)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._prompt_for(image.image_type)},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        request_size = len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode())

        common_fields = dict(
            image_id=image.image_id,
            image_type=image.image_type,
            product_code=image.product_code,
            sheet=image.sheet,
            anchor_row=image.anchor_row,
            anchor_column=image.anchor_column,
            image_sha256=prepared.sha256,
            mime_type=prepared.mime_type,
            width=prepared.width,
            height=prepared.height,
            bytes=len(prepared.data),
            original_width=image.width,
            original_height=image.height,
            original_bytes=len(image.data),
            preprocessing_version=PREPROCESSING_VERSION,
            request_size_bytes=request_size,
            prompt_version=prompt_version,
        )

        cached = None if refresh_cache else cache.get(cache_key)
        if cached:
            if image.image_type == "WASH_LABEL":
                evidence = WashLabelEvidence.model_validate(cached).model_copy(update={
                    **common_fields, "cache_status": "HIT", "llm_used": False, "latency_ms": 0,
                })
            else:
                evidence = HangtagEvidence.model_validate(cached).model_copy(update={
                    **common_fields, "cache_status": "HIT", "llm_used": False, "latency_ms": 0,
                })
            logger.info(
                "label_analysis file_id=%s code=%s image_id=%s type=%s cache=HIT llm_used=false",
                file_id, image.product_code, image.image_id, image.image_type,
            )
            return evidence, 0, 1, 0

        calls = 0
        latency = 0
        model = self.settings.omniroute_vision_model
        validated = None
        last_error = "INVALID_LABEL_JSON"
        for attempt in range(2):
            try:
                async with _LABEL_SEMAPHORE:
                    completion = await self.gateway.complete_vision_json(
                        messages, timeout_seconds=self.settings.visual_analysis_timeout_seconds
                    )
                calls += 1
                latency += completion.latency_ms
                model = completion.model or model
                parsed = _parse_json(completion.content)
                if image.image_type == "WASH_LABEL":
                    attributes = _calibrate_wash(LlmWashLabelAttributes.model_validate(parsed))
                    total, valid = _validate_composition_sum(attributes.composition)
                    status = "OK" if attributes.readable else "UNREADABLE"
                    if not attributes.readable:
                        status = "UNREADABLE"
                    elif attributes.uncertain_text:
                        status = "PARTIAL"
                    evidence = WashLabelEvidence(
                        **attributes.model_dump(),
                        evidence_id="WASH-001",
                        model=model,
                        latency_ms=latency,
                        cache_status="MISS",
                        llm_used=True,
                        status=status,
                        composition_sum=total,
                        composition_sum_valid=valid,
                        **common_fields,
                    )
                else:
                    attributes = _calibrate_hangtag(LlmHangtagAttributes.model_validate(parsed))
                    total, valid = _validate_composition_sum(attributes.composition)
                    status = "OK" if attributes.readable else "UNREADABLE"
                    if not attributes.readable:
                        status = "UNREADABLE"
                    elif attributes.uncertain_text:
                        status = "PARTIAL"
                    attrs_dict = attributes.model_dump()
                    # O campo "model" (LabeledField) conflita com o parâmetro "model" (nome do modelo IA).
                    hangtag_model_field = attrs_dict.pop("model", None)
                    evidence = HangtagEvidence(
                        **attrs_dict,
                        model=hangtag_model_field,
                        evidence_id="HANGTAG-001",
                        model_used=model,
                        latency_ms=latency,
                        cache_status="MISS",
                        llm_used=True,
                        status=status,
                        composition_sum=total,
                        composition_sum_valid=valid,
                        **common_fields,
                    )
                validated = evidence
                break
            except OmniRouteError:
                calls += 1
                raise
            except (json.JSONDecodeError, ValidationError, LabelAnalysisError) as exc:
                last_error = type(exc).__name__
                diagnostic = " ".join(str(exc).split())[:500]
                logger.warning(
                    "label_validation file_id=%s code=%s type=%s attempt=%s error=%s detail=%s",
                    file_id, image.product_code, image.image_type, attempt + 1,
                    last_error, diagnostic,
                )
                if attempt == 0:
                    messages.append({"role": "user", "content": (
                        "The prior output was invalid. Return only the exact JSON schema. "
                        "Use UNKNOWN for illegible text and never invent percentages or characters."
                    )})

        if validated is None:
            raise LabelAnalysisError(last_error)

        cache.put(cache_key, validated.model_dump(mode="json"))
        logger.info(
            "label_analysis file_id=%s code=%s image_id=%s type=%s prompt=%s model=%s llm_used=true cache=MISS latency_ms=%s status=%s",
            file_id, image.product_code, image.image_id, image.image_type,
            prompt_version, model, latency, validated.status,
        )
        return validated, calls, 0, 1
