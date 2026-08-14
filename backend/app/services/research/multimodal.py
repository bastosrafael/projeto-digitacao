from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis import (
    AnalysisValidationError,
    _build_evidence_package,
    _entry_contains,
    _parse_json,
)
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.multimodal_schemas import (
    LlmMultimodalAnalysis,
    MultimodalResponse,
    ProductMultimodalResult,
    VisualEvidence,
)
from app.services.research.schemas import EnrichmentResponse
from app.services.research.visual_analysis import VisualAnalysisError, VisualAnalysisService
from app.services.spreadsheets.images import ExtractedProductImage
from app.services.spreadsheets.schemas import Product

logger = logging.getLogger(__name__)

PROMPT_VERSION = "multimodal-evidence-analysis-v1"
ANALYSIS_VERSION = "multimodal-analysis-v1"
VISUAL_EVIDENCE_ID = "VISUAL-001"
ALL_FIELDS = (
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories", "category_visual", "primary_color", "sleeves",
    "straps", "length", "visible_details",
)
VISUAL_FIELDS = {"category_visual", "primary_color", "sleeves", "straps", "length", "visible_details"}
VISUAL_PROHIBITED_FIELDS = set(ALL_FIELDS) - VISUAL_FIELDS

_TEXT_SEMAPHORE = asyncio.Semaphore(1)


def _system_prompt() -> str:
    return files("app.prompts").joinpath("multimodal_evidence_analysis_v1.txt").read_text(encoding="utf-8")


def _visual_registry_entry(visual: VisualEvidence) -> dict[str, Any]:
    visible_details = [item.value for item in visual.observable_attributes.visible_details]
    return {
        "evidence_id": VISUAL_EVIDENCE_ID,
        "type": "visual_product_image",
        "image_id": visual.image_id,
        "image_type": visual.image_type,
        "product_code": visual.product_code,
        "observable_attributes": visual.observable_attributes.model_dump(mode="json"),
        "visible_details_summary": ", ".join(visible_details),
        "uncertain_attributes": [item.model_dump(mode="json") for item in visual.uncertain_attributes],
        "unknown_attributes": visual.unknown_attributes,
        "warnings": visual.warnings,
        "image_sha256": visual.image_sha256,
        "model": visual.model,
        "prompt_version": visual.prompt_version,
    }


def _external_support(package: dict[str, Any]) -> str:
    web = package["web_evidence"]
    strong_search = [
        item for item in package["search_evidence"]
        if item["strength"] == "STRONG" and item["source_category"] in {"MANUFACTURER", "SUPPLIER"}
    ]
    identity_web = [
        item for item in web
        if "code" in item["matched_signals"]
        and set(item["matched_signals"]) & {"item_name", "manufacturer", "brand"}
    ]
    if identity_web and (strong_search or len({item["domain"] for item in identity_web}) >= 2):
        return "STRONG"
    if package["search_evidence"] or web:
        return "LIMITED"
    return "NONE"


def _validate_multimodal(
    analysis: LlmMultimodalAnalysis,
    registry: dict[str, dict[str, Any]],
    package: dict[str, Any],
    visual: VisualEvidence | None,
) -> LlmMultimodalAnalysis:
    if visual and visual.uncertain_attributes:
        uncertain_fields = {item.field for item in visual.uncertain_attributes}
        removed = [item.field for item in analysis.confirmed_fields if item.field in uncertain_fields]
        if removed:
            analysis = analysis.model_copy(update={
                "confirmed_fields": [
                    item for item in analysis.confirmed_fields if item.field not in uncertain_fields
                ],
                "warnings": analysis.warnings + [
                    "Campos visuais incertos não foram promovidos: " + ", ".join(sorted(set(removed))) + "."
                ],
            })
    valid_ids = set(registry)
    used_ids = set(analysis.evidence_used)
    referenced = set(used_ids)
    for item in analysis.confirmed_fields:
        referenced.update(item.evidence_ids)
    for conflict in analysis.conflicts:
        referenced.update(source.evidence_id for source in conflict.sources)
    invalid = sorted(referenced - valid_ids)
    if invalid:
        raise AnalysisValidationError(f"evidence_ids inexistentes: {', '.join(invalid)}")
    for confirmed in analysis.confirmed_fields:
        if not set(confirmed.evidence_ids) <= used_ids:
            raise AnalysisValidationError("confirmed_fields deve usar IDs presentes em evidence_used")
        if not any(_entry_contains(registry[item], confirmed.value) for item in confirmed.evidence_ids):
            raise AnalysisValidationError(f"valor confirmado sem suporte: {confirmed.field}")
        if confirmed.field in VISUAL_PROHIBITED_FIELDS and VISUAL_EVIDENCE_ID in confirmed.evidence_ids:
            nonvisual_ids = [item for item in confirmed.evidence_ids if item != VISUAL_EVIDENCE_ID]
            if not nonvisual_ids or not any(
                _entry_contains(registry[item], confirmed.value) for item in nonvisual_ids
            ):
                raise AnalysisValidationError(f"VISUAL não comprova isoladamente: {confirmed.field}")
    for conflict in analysis.conflicts:
        ids = {source.evidence_id for source in conflict.sources}
        if not ids <= used_ids or len(ids) < 2:
            raise AnalysisValidationError("conflito deve citar ao menos duas evidências usadas")
        for source in conflict.sources:
            if not _entry_contains(registry[source.evidence_id], source.value):
                raise AnalysisValidationError(f"valor conflitante sem suporte: {conflict.field}")

    known_web_conflicts = {
        conflict["field"]
        for item in package["web_evidence"]
        for conflict in item.get("conflicts", [])
    }
    returned_conflicts = {item.field for item in analysis.conflicts}
    if known_web_conflicts - returned_conflicts:
        raise AnalysisValidationError("conflito conhecido foi omitido")

    confirmed_fields = {item.field for item in analysis.confirmed_fields}
    conflict_fields = returned_conflicts
    unknown_fields = set(analysis.unknown_fields)
    if confirmed_fields & conflict_fields or confirmed_fields & unknown_fields or conflict_fields & unknown_fields:
        raise AnalysisValidationError("campos confirmados, conflitantes e desconhecidos devem ser distintos")
    expected_unknown = set(ALL_FIELDS) - confirmed_fields - conflict_fields
    analysis = analysis.model_copy(update={
        "unknown_fields": [field for field in ALL_FIELDS if field in expected_unknown],
    })

    support = _external_support(package)
    has_visual_signal = bool(visual and any(
        getattr(visual.observable_attributes, field).value.casefold() != "unknown"
        for field in ("category_visual", "primary_color", "sleeves", "straps", "length")
    ))
    visual_ambiguous = bool(visual and visual.uncertain_attributes)
    decision = analysis.decision
    warnings = list(analysis.warnings)
    if conflict_fields:
        decision = "REVIEW"
    elif decision == "FOUND" and support != "STRONG":
        decision = "REVIEW" if has_visual_signal or support == "LIMITED" else "NOT_FOUND"
        warnings.append("FOUND rebaixado: evidência externa forte ausente.")
    elif support == "NONE":
        decision = "REVIEW" if has_visual_signal else "NOT_FOUND"
    if visual_ambiguous and decision != "NOT_FOUND":
        decision = "REVIEW"
    internal = analysis.internal_visual_match
    visual_conflict = any(
        any(source.evidence_id == VISUAL_EVIDENCE_ID for source in conflict.sources)
        for conflict in analysis.conflicts
    )
    if visual_conflict:
        internal = "CONFLICTING"
    elif visual is None:
        internal = "UNCERTAIN"
    elif visual_ambiguous and internal == "CONSISTENT":
        internal = "UNCERTAIN"
    confidence = "HIGH" if decision == "FOUND" and support == "STRONG" else (
        "MEDIUM" if decision == "REVIEW" and (has_visual_signal or package["web_evidence"]) else "LOW"
    )
    return analysis.model_copy(update={
        "decision": decision,
        "confidence": confidence,
        "internal_visual_match": internal,
        "external_support": support,
        "warnings": list(dict.fromkeys(warnings))[:20],
    })


def _controlled_review(
    product: Product,
    visual: VisualEvidence | None,
    *,
    visual_error: str | None = None,
    llm_error: str | None = None,
    llm_used_text: bool = False,
    textual_model: str | None = None,
    latency_ms: int = 0,
    evidence_count: int = 0,
    input_chars: int = 0,
) -> ProductMultimodalResult:
    return ProductMultimodalResult(
        product_id=product.product_id, code=product.code, decision="REVIEW", confidence="LOW",
        internal_visual_match="UNCERTAIN", external_support="NONE", confirmed_fields=[], conflicts=[],
        unknown_fields=list(ALL_FIELDS), reasoning_summary="A análise multimodal não pôde ser validada; revisão humana necessária.",
        evidence_used=[], warnings=["Análise multimodal indisponível ou inválida."],
        visual_used=visual is not None, visual_evidence=visual,
        llm_used_visual=bool(visual and visual.llm_used), llm_used_text=llm_used_text,
        visual_error=visual_error, llm_error=llm_error, textual_model=textual_model,
        textual_latency_ms=latency_ms, prompt_version=PROMPT_VERSION,
        analysis_version=ANALYSIS_VERSION, evidence_count=evidence_count,
        input_chars=input_chars, cache_status="MISS",
    )


class MultimodalAnalysisService:
    def __init__(
        self,
        settings: Settings,
        *,
        visual_service: VisualAnalysisService | None = None,
        gateway: OmniRouteService | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.visual_service = visual_service or VisualAnalysisService(settings)
        self.cache = cache or AnalysisCache(
            settings.multimodal_analysis_cache_dir,
            settings.multimodal_analysis_cache_ttl_seconds,
        )

    async def analyze(
        self,
        file_id: str,
        products: list[Product],
        images: dict[str, ExtractedProductImage | str | None],
        enrichment: EnrichmentResponse,
        *,
        refresh_visual_cache: bool,
        refresh_multimodal_cache: bool,
    ) -> MultimodalResponse:
        researched_by_id = {item.product_id: item for item in enrichment.research.products}
        enriched_by_id = {item.product_id: item for item in enrichment.products}
        results: list[ProductMultimodalResult] = []
        visual_calls = text_calls = visual_hits = visual_misses = final_hits = final_misses = 0

        for product in products:
            product_text_calls = 0
            visual = None
            visual_error = None
            selected = images.get(product.product_id)
            if isinstance(selected, str):
                visual_error = selected
            elif selected is not None:
                try:
                    visual, calls, hits, misses = await self.visual_service.analyze(
                        file_id, selected, refresh_cache=refresh_visual_cache
                    )
                    visual_calls += calls
                    visual_hits += hits
                    visual_misses += misses
                except (VisualAnalysisError, OmniRouteError) as exc:
                    visual_error = type(exc).__name__
            researched = researched_by_id[product.product_id]
            enriched = enriched_by_id[product.product_id]
            package, registry = _build_evidence_package(product, researched.evidences, enriched)
            if visual:
                visual_entry = _visual_registry_entry(visual)
                package["visual_evidence"] = [visual_entry]
                registry[VISUAL_EVIDENCE_ID] = visual_entry
            else:
                package["visual_evidence"] = []
            serialized = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(serialized) > self.settings.multimodal_analysis_max_input_chars:
                results.append(_controlled_review(
                    product, visual, visual_error=visual_error, llm_error="INPUT_TOO_LARGE",
                    evidence_count=len(registry), input_chars=len(serialized),
                ))
                continue
            identity = {
                "analysis_version": ANALYSIS_VERSION,
                "prompt_version": PROMPT_VERSION,
                "product": package["product"],
                "evidence_hash": hashlib.sha256(serialized.encode()).hexdigest(),
                "text_model": self.settings.omniroute_model,
            }
            cache_key = self.cache.key(identity)
            cached = None if refresh_multimodal_cache else self.cache.get(cache_key)
            if cached:
                result = ProductMultimodalResult.model_validate(cached)
                visual_cached = visual or result.visual_evidence
                if visual_cached:
                    visual_cached = visual_cached.model_copy(update={"llm_used": False, "cache_status": "HIT", "latency_ms": 0})
                result = result.model_copy(update={
                    "cache_status": "HIT", "llm_used_text": False,
                    "llm_used_visual": False, "textual_latency_ms": 0,
                    "visual_evidence": visual_cached, "visual_error": visual_error,
                })
                results.append(result)
                final_hits += 1
                continue
            final_misses += 1
            messages = [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": serialized},
            ]
            validated = None
            model = None
            latency = 0
            last_error = "INVALID_MULTIMODAL_JSON"
            for attempt in range(2):
                try:
                    async with _TEXT_SEMAPHORE:
                        completion = await self.gateway.complete_json(
                            messages, timeout_seconds=self.settings.multimodal_analysis_timeout_seconds
                        )
                    text_calls += 1
                    product_text_calls += 1
                    model = completion.model
                    latency += completion.latency_ms
                    parsed = LlmMultimodalAnalysis.model_validate(_parse_json(completion.content))
                    validated = _validate_multimodal(parsed, registry, package, visual)
                    break
                except OmniRouteError:
                    text_calls += 1
                    product_text_calls += 1
                    last_error = "LLM_UNAVAILABLE"
                    break
                except (json.JSONDecodeError, ValidationError, AnalysisValidationError) as exc:
                    last_error = type(exc).__name__
                    diagnostic = " ".join(str(exc).split())[:500]
                    logger.warning(
                        "multimodal_validation file_id=%s code=%s attempt=%s error=%s detail=%s",
                        file_id, product.code or product.product_id, attempt + 1,
                        last_error, diagnostic,
                    )
                    if attempt == 0:
                        messages.append({"role": "user", "content": (
                            "The prior response was invalid. Return only the exact JSON schema, preserve conflicts, "
                            "use only supplied evidence_ids, and never use VISUAL evidence to prove invisible fields."
                        )})
            if validated is None:
                results.append(_controlled_review(
                    product, visual, visual_error=visual_error, llm_error=last_error,
                    llm_used_text=product_text_calls > 0, textual_model=model, latency_ms=latency,
                    evidence_count=len(registry), input_chars=len(serialized),
                ))
                continue
            result = ProductMultimodalResult(
                **validated.model_dump(), product_id=product.product_id, code=product.code,
                visual_used=visual is not None, visual_evidence=visual,
                llm_used_visual=bool(visual and visual.llm_used), llm_used_text=True,
                visual_error=visual_error, textual_model=model, textual_latency_ms=latency,
                prompt_version=PROMPT_VERSION, analysis_version=ANALYSIS_VERSION,
                evidence_count=len(registry), input_chars=len(serialized), cache_status="MISS",
            )
            self.cache.put(cache_key, result.model_dump(mode="json"))
            results.append(result)
            logger.info(
                "multimodal_analysis file_id=%s code=%s image_id=%s prompt=%s visual_model=%s text_model=%s llm_used_visual=%s llm_used_text=true visual_cache=%s multimodal_cache=MISS decision=%s confidence=%s latency_ms=%s",
                file_id, product.code or product.product_id, visual.image_id if visual else "none",
                PROMPT_VERSION, visual.model if visual else "none", model or "unknown",
                bool(visual and visual.llm_used), visual.cache_status if visual else "SKIP",
                result.decision, result.confidence, latency,
            )
        return MultimodalResponse(
            file_id=file_id, products=results, visual_llm_calls=visual_calls,
            textual_llm_calls=text_calls, visual_cache_hits=visual_hits,
            visual_cache_misses=visual_misses, multimodal_cache_hits=final_hits,
            multimodal_cache_misses=final_misses,
            llm_used_visual=any(item.llm_used_visual for item in results),
            llm_used_text=any(item.llm_used_text for item in results),
        )
