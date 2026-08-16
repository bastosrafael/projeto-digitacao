from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from pydantic import ValidationError

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.multimodal_schemas import (
    LlmVisualAttributes,
    UncertainVisualAttribute,
    VisualAttribute,
    VisualEvidence,
)
from app.services.spreadsheets.images import ExtractedProductImage

logger = logging.getLogger(__name__)

PROMPT_VERSION = "visual-attribute-extraction-v1"
ANALYSIS_VERSION = "visual-analysis-v1"
PREPROCESSING_VERSION = "visual-image-normalization-v1"
PROHIBITED_VISUAL_FIELDS = (
    "composition", "fiber_percentages", "ncm", "manufacturer", "supplier", "sku",
    "chemical_material", "fabric_weight", "internal_properties",
)


class VisualAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    sha256: str


_VISION_SEMAPHORE = asyncio.Semaphore(1)


def _system_prompt() -> str:
    return files("app.prompts").joinpath("visual_attribute_extraction_v1.txt").read_text(encoding="utf-8")


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise VisualAnalysisError("a resposta visual não é um objeto JSON")
    return value


def prepare_image(image: ExtractedProductImage, *, max_bytes: int, max_side: int) -> PreparedImage:
    if image.mime_type not in {"image/jpeg", "image/png"}:
        raise VisualAnalysisError("Somente imagens JPEG e PNG são aceitas.")
    try:
        with Image.open(io.BytesIO(image.data)) as opened:
            opened.load()
            normalized = ImageOps.exif_transpose(opened)
            needs_resize = max(normalized.size) > max_side
            needs_reencode = len(image.data) > max_bytes or needs_resize
            if not needs_reencode:
                return PreparedImage(
                    data=image.data, mime_type=image.mime_type, width=normalized.width,
                    height=normalized.height, sha256=image.sha256,
                )
            normalized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            if normalized.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", normalized.size, "white")
                background.paste(normalized, mask=normalized.getchannel("A"))
                normalized = background
            elif normalized.mode != "RGB":
                normalized = normalized.convert("RGB")
            encoded = b""
            for quality in (88, 80, 72, 64, 55, 45):
                output = io.BytesIO()
                normalized.save(output, format="JPEG", quality=quality, optimize=True)
                encoded = output.getvalue()
                if len(encoded) <= max_bytes:
                    break
            if len(encoded) > max_bytes:
                raise VisualAnalysisError("A imagem não pôde ser normalizada para o limite configurado.")
            return PreparedImage(
                data=encoded, mime_type="image/jpeg", width=normalized.width,
                height=normalized.height, sha256=hashlib.sha256(encoded).hexdigest(),
            )
    except (OSError, ValueError) as exc:
        if isinstance(exc, VisualAnalysisError):
            raise
        raise VisualAnalysisError("A imagem associada não pôde ser decodificada.") from exc


def _calibrate_visual(value: LlmVisualAttributes) -> LlmVisualAttributes:
    attrs = value.observable_attributes
    updates: dict[str, VisualAttribute] = {}
    uncertain = list(value.uncertain_attributes)
    warnings = list(value.warnings)
    for field in ("category_visual", "primary_color", "sleeves", "straps", "length"):
        item = getattr(attrs, field)
        if item.value.casefold() == "unknown" and item.confidence != "LOW":
            updates[field] = item.model_copy(update={"confidence": "LOW"})
    sleeves = attrs.sleeves
    straps = attrs.straps
    if sleeves.value.casefold() != "unknown" and straps.value.casefold() != "unknown":
        uncertain.extend([
            UncertainVisualAttribute(
                field="sleeves", candidate_values=[sleeves.value, "UNKNOWN"],
                reason="Sleeves and straps are simultaneously visible or ambiguous; certainty was reduced.",
            ),
            UncertainVisualAttribute(
                field="straps", candidate_values=[straps.value, "UNKNOWN"],
                reason="Sleeves and straps are simultaneously visible or ambiguous; certainty was reduced.",
            ),
        ])
        updates["sleeves"] = VisualAttribute(value="UNKNOWN", confidence="LOW")
        updates["straps"] = VisualAttribute(value="UNKNOWN", confidence="LOW")
        warnings.append("Ambiguous sleeves/straps interpretation was normalized to UNKNOWN.")
    if updates:
        attrs = attrs.model_copy(update=updates)
    unknown = list(dict.fromkeys([*value.unknown_attributes, *PROHIBITED_VISUAL_FIELDS]))
    return value.model_copy(update={
        "observable_attributes": attrs,
        "uncertain_attributes": uncertain[:10],
        "unknown_attributes": unknown[:30],
        "warnings": list(dict.fromkeys(warnings))[:20],
    })


class VisualAnalysisService:
    def __init__(
        self,
        settings: Settings,
        gateway: OmniRouteService | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.cache = cache or AnalysisCache(
            settings.visual_analysis_cache_dir, settings.visual_analysis_cache_ttl_seconds
        )

    async def analyze(
        self,
        file_id: str,
        image: ExtractedProductImage,
        *,
        refresh_cache: bool,
    ) -> tuple[VisualEvidence, int, int, int]:
        prepared = prepare_image(
            image,
            max_bytes=self.settings.visual_image_max_bytes,
            max_side=self.settings.visual_image_max_side,
        )
        identity = {
            "analysis_version": ANALYSIS_VERSION,
            "image_hash": prepared.sha256,
            "product_code": image.product_code,
            "prompt_version": PROMPT_VERSION,
            "vision_model": self.settings.omniroute_vision_model,
            "image_type": image.image_type,
            "preprocessing_version": PREPROCESSING_VERSION,
        }
        cache_key = self.cache.key(identity)
        data_url = f"data:{prepared.mime_type};base64,{base64.b64encode(prepared.data).decode('ascii')}"
        user_text = json.dumps({
            "image_id": image.image_id,
            "image_type": image.image_type,
            "product_code": image.product_code,
        }, ensure_ascii=False)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        request_size = len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode())
        cached = None if refresh_cache else self.cache.get(cache_key)
        if cached:
            evidence = VisualEvidence.model_validate(cached).model_copy(update={
                "image_id": image.image_id, "image_type": image.image_type,
                "product_code": image.product_code, "sheet": image.sheet,
                "anchor_row": image.anchor_row, "anchor_column": image.anchor_column,
                "image_sha256": prepared.sha256, "mime_type": prepared.mime_type,
                "width": prepared.width, "height": prepared.height, "bytes": len(prepared.data),
                "original_width": image.width, "original_height": image.height,
                "original_bytes": len(image.data), "request_size_bytes": request_size,
                "cache_status": "HIT", "llm_used": False, "latency_ms": 0,
            })
            logger.info(
                "visual_analysis file_id=%s code=%s image_id=%s image_hash=%s bytes=%s mime=%s dimensions=%sx%s prompt=%s model=%s llm_used=false cache=HIT latency_ms=0",
                file_id, image.product_code, image.image_id, prepared.sha256, len(prepared.data),
                prepared.mime_type, prepared.width, prepared.height, PROMPT_VERSION,
                self.settings.omniroute_vision_model,
            )
            return evidence, 0, 1, 0

        calls = 0
        latency = 0
        model = self.settings.omniroute_vision_model
        fallback_used = False
        fallback_reason = None
        last_error = "INVALID_VISUAL_JSON"
        validated: LlmVisualAttributes | None = None
        for attempt in range(2):
            try:
                async with _VISION_SEMAPHORE:
                    completion = await self.gateway.complete_vision_json(
                        messages, timeout_seconds=self.settings.visual_analysis_timeout_seconds
                    )
                calls += 1
                latency += completion.latency_ms
                model = completion.model or model
                fallback_used = completion.fallback_used
                fallback_reason = completion.fallback_reason
                validated = _calibrate_visual(
                    LlmVisualAttributes.model_validate(_parse_json(completion.content))
                )
                break
            except OmniRouteError:
                calls += 1
                raise
            except (json.JSONDecodeError, ValidationError, VisualAnalysisError) as exc:
                last_error = type(exc).__name__
                if attempt == 0:
                    messages.append({"role": "user", "content": (
                        "The prior output was invalid. Re-inspect the same image and return only the exact JSON schema. "
                        "Use UNKNOWN/LOW for ambiguity and do not add fields."
                    )})
        if validated is None:
            raise VisualAnalysisError(last_error)
        evidence = VisualEvidence(
            **validated.model_dump(), evidence_id="VISUAL-001", image_id=image.image_id,
            image_type="PRODUCT_IMAGE", product_code=image.product_code, sheet=image.sheet,
            anchor_row=image.anchor_row, anchor_column=image.anchor_column,
            image_sha256=prepared.sha256, mime_type=prepared.mime_type,
            width=prepared.width, height=prepared.height, bytes=len(prepared.data),
            original_width=image.width, original_height=image.height, original_bytes=len(image.data),
            preprocessing_version=PREPROCESSING_VERSION, request_size_bytes=request_size,
            model=model, prompt_version=PROMPT_VERSION, latency_ms=latency,
            cache_status="MISS", llm_used=True,
        )
        self.cache.put(cache_key, evidence.model_dump(mode="json"))
        logger.info(
            "visual_analysis file_id=%s code=%s image_id=%s image_hash=%s bytes=%s mime=%s dimensions=%sx%s request_bytes=%s prompt=%s model=%s fallback_used=%s fallback_reason=%s llm_used=true cache=MISS latency_ms=%s",
            file_id, image.product_code, image.image_id, prepared.sha256, len(prepared.data),
            prepared.mime_type, prepared.width, prepared.height, request_size, PROMPT_VERSION,
            model, fallback_used, fallback_reason, latency,
        )
        return evidence, calls, 0, 1
