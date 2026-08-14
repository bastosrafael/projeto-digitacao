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
from app.services.research.label_analysis import LabelAnalysisError, LabelAnalysisService
from app.services.research.label_schemas import HangtagEvidence, WashLabelEvidence
from app.services.research.labels_multimodal_schemas import (
    LabelStatusEntry,
    LabelsConflict,
    LabelsConflictSource,
    LabelsConfirmedField,
    LabelsMultimodalResponse,
    LlmLabelsCrossAnalysis,
    ProductLabelsMultimodalResult,
)
from app.services.research.multimodal_schemas import VisualEvidence
from app.services.research.schemas import EnrichmentResponse
from app.services.research.visual_analysis import VisualAnalysisError, VisualAnalysisService
from app.services.spreadsheets.images import ExtractedProductImage
from app.services.spreadsheets.schemas import Product

logger = logging.getLogger(__name__)

PROMPT_VERSION = "labels-multimodal-analysis-v1"
ANALYSIS_VERSION = "labels-multimodal-analysis-v1"
VISUAL_EVIDENCE_ID = "VISUAL-001"
WASH_EVIDENCE_ID = "WASH-001"
HANGTAG_EVIDENCE_ID = "HANGTAG-001"

LABEL_FIELDS = (
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories", "category_visual", "primary_color", "sleeves",
    "straps", "length", "visible_details", "country_of_origin", "material",
    "style_code_from_label", "sku_from_label", "barcode_text",
)

VISUAL_ONLY_FIELDS = {"category_visual", "primary_color", "sleeves", "straps", "length", "visible_details"}
NON_VISUAL_PROOF_FIELDS = set(LABEL_FIELDS) - VISUAL_ONLY_FIELDS
WASH_STRONG_FIELDS = {"composition", "size", "country_of_origin", "brand", "style_code_from_label"}
HANGTAG_STRONG_FIELDS = {"brand", "style_code_from_label", "size", "color", "sku_from_label", "barcode_text"}

_TEXT_SEMAPHORE = asyncio.Semaphore(1)


def _system_prompt() -> str:
    return files("app.prompts").joinpath("labels_multimodal_analysis_v1.txt").read_text(encoding="utf-8")


def _wash_registry_entry(wash: WashLabelEvidence) -> dict[str, Any]:
    return {
        "evidence_id": WASH_EVIDENCE_ID,
        "type": "wash_label_evidence",
        "image_id": wash.image_id,
        "image_type": wash.image_type,
        "readable": wash.readable,
        "status": wash.status,
        "raw_visible_text": [item.model_dump(mode="json") for item in wash.raw_visible_text],
        "composition": [item.model_dump(mode="json") for item in wash.composition],
        "composition_sum": wash.composition_sum,
        "composition_sum_valid": wash.composition_sum_valid,
        "size": wash.size.model_dump(mode="json"),
        "country_of_origin": wash.country_of_origin.model_dump(mode="json"),
        "brand": wash.brand.model_dump(mode="json"),
        "style_code": wash.style_code.model_dump(mode="json"),
        "care_instructions": wash.care_instructions,
        "uncertain_text": [item.model_dump(mode="json") for item in wash.uncertain_text],
        "unknown_fields": wash.unknown_fields,
        "warnings": wash.warnings,
        "image_sha256": wash.image_sha256,
        "model": wash.model,
        "prompt_version": wash.prompt_version,
    }


def _hangtag_registry_entry(ht: HangtagEvidence) -> dict[str, Any]:
    return {
        "evidence_id": HANGTAG_EVIDENCE_ID,
        "type": "hangtag_evidence",
        "image_id": ht.image_id,
        "image_type": ht.image_type,
        "readable": ht.readable,
        "status": ht.status,
        "raw_visible_text": [item.model_dump(mode="json") for item in ht.raw_visible_text],
        "brand": ht.brand.model_dump(mode="json"),
        "style_code": ht.style_code.model_dump(mode="json"),
        "model": ht.model.model_dump(mode="json"),
        "size": ht.size.model_dump(mode="json"),
        "declared_color": ht.declared_color.model_dump(mode="json"),
        "sku": ht.sku.model_dump(mode="json"),
        "reference": ht.reference.model_dump(mode="json"),
        "visible_barcode_text": ht.visible_barcode_text.model_dump(mode="json"),
        "composition": [item.model_dump(mode="json") for item in ht.composition],
        "material": ht.material.model_dump(mode="json"),
        "country": ht.country.model_dump(mode="json"),
        "uncertain_text": [item.model_dump(mode="json") for item in ht.uncertain_text],
        "unknown_fields": ht.unknown_fields,
        "warnings": ht.warnings,
        "image_sha256": ht.image_sha256,
        "model_used": ht.model_used,
        "prompt_version": ht.prompt_version,
    }


def _visual_registry_entry(visual: VisualEvidence) -> dict[str, Any]:
    visible_details = [item.value for item in visual.observable_attributes.visible_details]
    return {
        "evidence_id": VISUAL_EVIDENCE_ID,
        "type": "visual_product_image",
        "image_id": visual.image_id,
        "image_type": visual.image_type,
        "observable_attributes": visual.observable_attributes.model_dump(mode="json"),
        "visible_details_summary": ", ".join(visible_details),
        "uncertain_attributes": [item.model_dump(mode="json") for item in visual.uncertain_attributes],
        "unknown_attributes": visual.unknown_attributes,
        "image_sha256": visual.image_sha256,
        "model": visual.model,
        "prompt_version": visual.prompt_version,
    }


def _compute_internal_support(
    product: Product,
    visual: VisualEvidence | None,
    wash: WashLabelEvidence | None,
    hangtag: HangtagEvidence | None,
) -> str:
    signals = 0
    code_confirmed = False
    composition_compatible = False
    no_material_conflict = True

    if product.code:
        if hangtag and hangtag.readable and hangtag.style_code.value.casefold() != "unknown":
            if hangtag.style_code.value.casefold() == product.code.casefold():
                code_confirmed = True
                signals += 2
        if visual and visual.observable_attributes.category_visual.value.casefold() != "unknown":
            signals += 1

    if wash and wash.readable and wash.composition:
        packing_comp = (product.composition or "").casefold()
        if packing_comp:
            wash_fibers = " ".join(
                f"{item.fiber_normalized or item.fiber_original} {item.percentage or '?'}%"
                for item in wash.composition
                if item.confidence in ("HIGH", "MEDIUM")
            ).casefold()
            if any(
                token in wash_fibers
                for token in packing_comp.split()
                if len(token) > 2
            ):
                composition_compatible = True
                signals += 1
            elif wash.composition and any(item.percentage is not None for item in wash.composition):
                no_material_conflict = False

    if hangtag and hangtag.readable:
        if hangtag.brand.value.casefold() != "unknown" and product.brand:
            if hangtag.brand.value.casefold() in (product.brand or "").casefold():
                signals += 1
        if hangtag.size.value.casefold() != "unknown" and product.size:
            if hangtag.size.value.casefold() == (product.size or "").casefold():
                signals += 1

    if code_confirmed and composition_compatible and no_material_conflict and signals >= 3:
        return "STRONG"
    if signals >= 2:
        return "MODERATE"
    if signals >= 1:
        return "WEAK"
    return "NONE"


def _compute_external_support(package: dict[str, Any]) -> str:
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


def _validate_labels_analysis(
    analysis: LlmLabelsCrossAnalysis,
    registry: dict[str, dict[str, Any]],
    package: dict[str, Any],
    visual: VisualEvidence | None,
    wash: WashLabelEvidence | None,
    hangtag: HangtagEvidence | None,
) -> LlmLabelsCrossAnalysis:
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
        if confirmed.field in NON_VISUAL_PROOF_FIELDS and VISUAL_EVIDENCE_ID in confirmed.evidence_ids:
            nonvisual_ids = [eid for eid in confirmed.evidence_ids if eid != VISUAL_EVIDENCE_ID]
            if not nonvisual_ids or not any(
                _entry_contains(registry[eid], confirmed.value) for eid in nonvisual_ids
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
        raise AnalysisValidationError("conflito web conhecido foi omitido")

    if wash and wash.readable and wash.composition:
        product_composition = package["product"].get("composition")
        if product_composition and any(item.percentage is not None for item in wash.composition):
            wash_comp_text = " ".join(
                f"{item.fiber_normalized or item.fiber_original}"
                for item in wash.composition if item.confidence in ("HIGH", "MEDIUM")
            ).casefold()
            packing_comp = product_composition.casefold()
            if wash_comp_text and packing_comp and not any(
                token in wash_comp_text for token in packing_comp.split() if len(token) > 2
            ):
                if "composition" not in returned_conflicts:
                    analysis = analysis.model_copy(update={
                        "conflicts": analysis.conflicts + [LabelsConflict(
                            field="composition",
                            sources=[
                                LabelsConflictSource(evidence_id="PACKING-001", evidence_type="packing_list", value=product_composition),
                                LabelsConflictSource(evidence_id=WASH_EVIDENCE_ID, evidence_type="wash_label", value=wash_comp_text.strip()),
                            ],
                        )],
                        "confirmed_fields": [
                            item for item in analysis.confirmed_fields if item.field != "composition"
                        ],
                    })

    confirmed_fields = {item.field for item in analysis.confirmed_fields}
    conflict_fields = {item.field for item in analysis.conflicts}
    unknown_fields = set(analysis.unknown_fields)
    if confirmed_fields & conflict_fields or confirmed_fields & unknown_fields or conflict_fields & unknown_fields:
        raise AnalysisValidationError("campos confirmados, conflitantes e desconhecidos devem ser distintos")

    internal = _compute_internal_support_from_evidence(analysis, visual, wash, hangtag)
    external = _compute_external_support(package)

    has_visual_signal = bool(visual and any(
        getattr(visual.observable_attributes, field).value.casefold() != "unknown"
        for field in ("category_visual", "primary_color", "sleeves", "straps", "length")
    ))
    has_label_signal = bool(
        (wash and wash.readable and wash.status in ("OK", "PARTIAL")) or
        (hangtag and hangtag.readable and hangtag.status in ("OK", "PARTIAL"))
    )
    has_conflicts = bool(analysis.conflicts)

    decision = analysis.decision
    warnings = list(analysis.warnings)
    if has_conflicts:
        decision = "REVIEW"
    elif decision == "FOUND" and external != "STRONG":
        if internal == "STRONG" and has_label_signal:
            decision = "REVIEW"
            warnings.append("FOUND rebaixado: evidência interna forte mas suporte externo insuficiente.")
        elif has_visual_signal or has_label_signal or external == "LIMITED":
            decision = "REVIEW"
            warnings.append("FOUND rebaixado: evidência externa forte ausente.")
        else:
            decision = "NOT_FOUND"
            warnings.append("FOUND rebaixado: sem suporte interno nem externo suficiente.")
    elif external == "NONE" and internal in ("NONE", "WEAK"):
        decision = "REVIEW" if (has_visual_signal or has_label_signal) else "NOT_FOUND"

    confidence = "HIGH" if decision == "FOUND" and external == "STRONG" else (
        "MEDIUM" if decision == "REVIEW" and (has_label_signal or internal != "NONE") else "LOW"
    )
    return analysis.model_copy(update={
        "decision": decision,
        "confidence": confidence,
        "internal_support": internal,
        "external_support": external,
        "warnings": list(dict.fromkeys(warnings))[:20],
    })


def _compute_internal_support_from_evidence(
    analysis: LlmLabelsCrossAnalysis,
    visual: VisualEvidence | None,
    wash: WashLabelEvidence | None,
    hangtag: HangtagEvidence | None,
) -> str:
    confirmed = {item.field for item in analysis.confirmed_fields}
    conflicts = {item.field for item in analysis.conflicts}
    signals = 0

    if "code" in confirmed or "style_code_from_label" in confirmed:
        signals += 2
    if visual and any(
        getattr(visual.observable_attributes, f).value.casefold() != "unknown"
        for f in ("category_visual", "primary_color", "length")
    ):
        signals += 1
    if wash and wash.readable and "composition" in confirmed:
        signals += 1
    if hangtag and hangtag.readable and any(f in confirmed for f in ("brand", "size", "color")):
        signals += 1
    if conflicts:
        signals = max(signals - len(conflicts), 0)

    if signals >= 4:
        return "STRONG"
    if signals >= 2:
        return "MODERATE"
    if signals >= 1:
        return "WEAK"
    return "NONE"


def _controlled_review(
    product: Product,
    *,
    visual: VisualEvidence | None = None,
    wash: WashLabelEvidence | None = None,
    hangtag: HangtagEvidence | None = None,
    label_statuses: list[LabelStatusEntry] | None = None,
    visual_error: str | None = None,
    wash_error: str | None = None,
    hangtag_error: str | None = None,
    llm_error: str | None = None,
    llm_used_text: bool = False,
    textual_model: str | None = None,
    latency_ms: int = 0,
    evidence_count: int = 0,
    input_chars: int = 0,
) -> ProductLabelsMultimodalResult:
    return ProductLabelsMultimodalResult(
        product_id=product.product_id, code=product.code, decision="REVIEW", confidence="LOW",
        internal_support="NONE", external_support="NONE", confirmed_fields=[], conflicts=[],
        unknown_fields=list(LABEL_FIELDS), reasoning_summary="A análise de labels não pôde ser validada; revisão humana necessária.",
        evidence_used=[], warnings=["Análise de labels indisponível ou inválida."],
        product_image_used=visual is not None, wash_label_used=wash is not None,
        hangtag_used=hangtag is not None,
        visual_evidence=visual, wash_label_evidence=wash, hangtag_evidence=hangtag,
        label_statuses=label_statuses or [],
        llm_used_visual=bool(visual and visual.llm_used),
        llm_used_wash=bool(wash and wash.llm_used),
        llm_used_hangtag=bool(hangtag and hangtag.llm_used),
        llm_used_text=llm_used_text,
        visual_error=visual_error, wash_error=wash_error, hangtag_error=hangtag_error,
        llm_error=llm_error, textual_model=textual_model, textual_latency_ms=latency_ms,
        prompt_version=PROMPT_VERSION, analysis_version=ANALYSIS_VERSION,
        evidence_count=evidence_count, input_chars=input_chars, cache_status="MISS",
    )


class LabelsMultimodalService:
    def __init__(
        self,
        settings: Settings,
        *,
        visual_service: VisualAnalysisService | None = None,
        label_service: LabelAnalysisService | None = None,
        gateway: OmniRouteService | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.visual_service = visual_service or VisualAnalysisService(settings)
        self.label_service = label_service or LabelAnalysisService(settings)
        self.cache = cache or AnalysisCache(
            settings.labels_multimodal_cache_dir, settings.labels_multimodal_cache_ttl_seconds
        )

    async def analyze(
        self,
        file_id: str,
        products: list[Product],
        product_images: dict[str, ExtractedProductImage | str | None],
        wash_images: dict[str, ExtractedProductImage | str | None],
        hangtag_images: dict[str, ExtractedProductImage | str | None],
        enrichment: EnrichmentResponse,
        *,
        refresh_visual_cache: bool,
        refresh_wash_cache: bool,
        refresh_hangtag_cache: bool,
        refresh_labels_cache: bool,
    ) -> LabelsMultimodalResponse:
        researched_by_id = {item.product_id: item for item in enrichment.research.products}
        enriched_by_id = {item.product_id: item for item in enrichment.products}
        results: list[ProductLabelsMultimodalResult] = []

        visual_calls = 0
        wash_calls = hangtag_calls = text_calls = 0
        visual_hits = wash_hits = hangtag_hits = labels_hits = labels_misses = 0

        for product in products:
            product_text_calls = 0
            visual = wash = hangtag = None
            visual_error = wash_error = hangtag_error = None
            label_statuses: list[LabelStatusEntry] = []

            # 1) Visual PRODUCT_IMAGE
            prod_img = product_images.get(product.product_id)
            if isinstance(prod_img, str):
                visual_error = prod_img
            elif prod_img is not None:
                try:
                    visual, v_calls, v_hits, _ = await self.visual_service.analyze(
                        file_id, prod_img, refresh_cache=refresh_visual_cache
                    )
                    visual_calls += v_calls
                    visual_hits += v_hits
                    label_statuses.append(LabelStatusEntry(
                        image_id=visual.image_id, image_type="PRODUCT_IMAGE", status="OK",
                    ))
                except (VisualAnalysisError, OmniRouteError) as exc:
                    visual_error = type(exc).__name__
                    label_statuses.append(LabelStatusEntry(
                        image_id=prod_img.image_id, image_type="PRODUCT_IMAGE",
                        status="ERROR", error=visual_error,
                    ))

            # 2) WASH_LABEL
            wash_img = wash_images.get(product.product_id)
            if isinstance(wash_img, str):
                wash_error = wash_img
                label_statuses.append(LabelStatusEntry(
                    image_id="none", image_type="WASH_LABEL", status="ERROR", error=wash_error,
                ))
            elif wash_img is not None:
                try:
                    wash, w_calls, w_hits, _ = await self.label_service.analyze_wash_label(
                        file_id, wash_img, refresh_cache=refresh_wash_cache
                    )
                    wash_calls += w_calls
                    wash_hits += w_hits
                    label_statuses.append(LabelStatusEntry(
                        image_id=wash.image_id, image_type="WASH_LABEL", status=wash.status,
                    ))
                except (LabelAnalysisError, OmniRouteError) as exc:
                    wash_error = type(exc).__name__
                    label_statuses.append(LabelStatusEntry(
                        image_id=wash_img.image_id, image_type="WASH_LABEL",
                        status="ERROR", error=wash_error,
                    ))
            else:
                label_statuses.append(LabelStatusEntry(
                    image_id="none", image_type="WASH_LABEL", status="NO_IMAGE",
                ))

            # 3) HANGTAG
            ht_img = hangtag_images.get(product.product_id)
            if isinstance(ht_img, str):
                hangtag_error = ht_img
                label_statuses.append(LabelStatusEntry(
                    image_id="none", image_type="HANGTAG", status="ERROR", error=hangtag_error,
                ))
            elif ht_img is not None:
                try:
                    hangtag, h_calls, h_hits, _ = await self.label_service.analyze_hangtag(
                        file_id, ht_img, refresh_cache=refresh_hangtag_cache
                    )
                    hangtag_calls += h_calls
                    hangtag_hits += h_hits
                    label_statuses.append(LabelStatusEntry(
                        image_id=hangtag.image_id, image_type="HANGTAG", status=hangtag.status,
                    ))
                except (LabelAnalysisError, OmniRouteError) as exc:
                    hangtag_error = type(exc).__name__
                    label_statuses.append(LabelStatusEntry(
                        image_id=ht_img.image_id, image_type="HANGTAG",
                        status="ERROR", error=hangtag_error,
                    ))
            else:
                label_statuses.append(LabelStatusEntry(
                    image_id="none", image_type="HANGTAG", status="NO_IMAGE",
                ))

            # 4) Build evidence package
            researched = researched_by_id[product.product_id]
            enriched = enriched_by_id[product.product_id]
            package, registry = _build_evidence_package(product, researched.evidences, enriched)

            if visual:
                visual_entry = _visual_registry_entry(visual)
                package["visual_evidence"] = [visual_entry]
                registry[VISUAL_EVIDENCE_ID] = visual_entry
            else:
                package["visual_evidence"] = []

            if wash and wash.readable:
                wash_entry = _wash_registry_entry(wash)
                package["wash_label_evidence"] = [wash_entry]
                registry[WASH_EVIDENCE_ID] = wash_entry
            else:
                package["wash_label_evidence"] = []

            if hangtag and hangtag.readable:
                ht_entry = _hangtag_registry_entry(hangtag)
                package["hangtag_evidence"] = [ht_entry]
                registry[HANGTAG_EVIDENCE_ID] = ht_entry
            else:
                package["hangtag_evidence"] = []

            serialized = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(serialized) > self.settings.multimodal_analysis_max_input_chars:
                results.append(_controlled_review(
                    product, visual=visual, wash=wash, hangtag=hangtag,
                    label_statuses=label_statuses, visual_error=visual_error,
                    wash_error=wash_error, hangtag_error=hangtag_error,
                    llm_error="INPUT_TOO_LARGE", evidence_count=len(registry), input_chars=len(serialized),
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
            cached = None if refresh_labels_cache else self.cache.get(cache_key)
            if cached:
                result = ProductLabelsMultimodalResult.model_validate(cached)
                if visual:
                    visual = visual.model_copy(update={"llm_used": False, "cache_status": "HIT", "latency_ms": 0})
                if wash:
                    wash = wash.model_copy(update={"llm_used": False, "cache_status": "HIT", "latency_ms": 0})
                if hangtag:
                    hangtag = hangtag.model_copy(update={"llm_used": False, "cache_status": "HIT", "latency_ms": 0})
                result = result.model_copy(update={
                    "cache_status": "HIT", "llm_used_text": False,
                    "llm_used_visual": False, "llm_used_wash": False, "llm_used_hangtag": False,
                    "textual_latency_ms": 0,
                    "visual_evidence": visual, "wash_label_evidence": wash,
                    "hangtag_evidence": hangtag,
                    "visual_error": visual_error, "wash_error": wash_error,
                    "hangtag_error": hangtag_error,
                    "label_statuses": label_statuses,
                })
                results.append(result)
                labels_hits += 1
                continue
            labels_misses += 1

            messages = [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": serialized},
            ]
            validated = None
            model = None
            latency = 0
            last_error = "INVALID_LABELS_JSON"
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
                    parsed = LlmLabelsCrossAnalysis.model_validate(_parse_json(completion.content))
                    validated = _validate_labels_analysis(
                        parsed, registry, package, visual, wash, hangtag
                    )
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
                        "labels_validation file_id=%s code=%s attempt=%s error=%s detail=%s",
                        file_id, product.code or product.product_id, attempt + 1,
                        last_error, diagnostic,
                    )
                    if attempt == 0:
                        messages.append({"role": "user", "content": (
                            "The prior response was invalid. Return only the exact JSON schema, "
                            "preserve conflicts, use only supplied evidence_ids, and never use "
                            "VISUAL evidence to prove invisible fields."
                        )})

            if validated is None:
                results.append(_controlled_review(
                    product, visual=visual, wash=wash, hangtag=hangtag,
                    label_statuses=label_statuses, visual_error=visual_error,
                    wash_error=wash_error, hangtag_error=hangtag_error,
                    llm_error=last_error, llm_used_text=product_text_calls > 0,
                    textual_model=model, latency_ms=latency,
                    evidence_count=len(registry), input_chars=len(serialized),
                ))
                continue

            result = ProductLabelsMultimodalResult(
                **validated.model_dump(), product_id=product.product_id, code=product.code,
                product_image_used=visual is not None, wash_label_used=wash is not None,
                hangtag_used=hangtag is not None,
                visual_evidence=visual, wash_label_evidence=wash, hangtag_evidence=hangtag,
                label_statuses=label_statuses,
                llm_used_visual=bool(visual and visual.llm_used),
                llm_used_wash=bool(wash and wash.llm_used),
                llm_used_hangtag=bool(hangtag and hangtag.llm_used),
                llm_used_text=True,
                visual_error=visual_error, wash_error=wash_error, hangtag_error=hangtag_error,
                textual_model=model, textual_latency_ms=latency,
                prompt_version=PROMPT_VERSION, analysis_version=ANALYSIS_VERSION,
                evidence_count=len(registry), input_chars=len(serialized), cache_status="MISS",
            )
            self.cache.put(cache_key, result.model_dump(mode="json"))
            results.append(result)
            logger.info(
                "labels_analysis file_id=%s code=%s prompt=%s visual=%s wash=%s hangtag=%s text_model=%s decision=%s confidence=%s internal=%s external=%s latency_ms=%s",
                file_id, product.code or product.product_id, PROMPT_VERSION,
                visual.image_id if visual else "none",
                wash.image_id if wash else "none",
                hangtag.image_id if hangtag else "none",
                model or "unknown", result.decision, result.confidence,
                result.internal_support, result.external_support, latency,
            )

        return LabelsMultimodalResponse(
            file_id=file_id, products=results,
            visual_llm_calls=visual_calls, wash_llm_calls=wash_calls,
            hangtag_llm_calls=hangtag_calls, textual_llm_calls=text_calls,
            visual_cache_hits=visual_hits, wash_cache_hits=wash_hits,
            hangtag_cache_hits=hangtag_hits, labels_cache_hits=labels_hits,
            labels_cache_misses=labels_misses,
            llm_used_visual=any(item.llm_used_visual for item in results),
            llm_used_wash=any(item.llm_used_wash for item in results),
            llm_used_hangtag=any(item.llm_used_hangtag for item in results),
            llm_used_text=any(item.llm_used_text for item in results),
        )
