from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.analysis_schemas import (
    AnalysisResponse,
    LlmEvidenceAnalysis,
    ProductAnalysisResult,
)
from app.services.research.schemas import EnrichmentResponse, ProductEnrichmentResult, ResearchEvidence
from app.services.spreadsheets.schemas import Product

logger = logging.getLogger(__name__)

PROMPT_VERSION = "evidence-analysis-v1"
ANALYSIS_VERSION = "llm-analysis-v1"
MAX_EXCERPT_CHARS = 2_500
MAX_SEARCH_EVIDENCES = 8
MAX_STRUCTURED_ITEMS = 3
PACKING_EVIDENCE_ID = "PACKING-001"
PRODUCT_FIELDS = (
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories",
)


class AnalysisValidationError(ValueError):
    pass


_LLM_SEMAPHORE = asyncio.Semaphore(1)


def _system_prompt() -> str:
    return files("app.prompts").joinpath("evidence_analysis_v1.txt").read_text(encoding="utf-8")


def _clean(value: str | None, limit: int) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def _product_payload(product: Product) -> dict[str, str]:
    payload = {
        field: _clean(str(value), 1_000)
        for field in PRODUCT_FIELDS
        if (value := getattr(product, field, None))
    }
    return {"evidence_id": PACKING_EVIDENCE_ID, **payload}


def _compact_structured_data(value: Any) -> Any:
    if isinstance(value, dict):
        compacted = {}
        for key, item in list(value.items())[:30]:
            compacted[_clean(str(key), 80)] = _compact_structured_data(item)
        return compacted
    if isinstance(value, list):
        return [_compact_structured_data(item) for item in value[:MAX_STRUCTURED_ITEMS]]
    if isinstance(value, str):
        return _clean(value, 500)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean(str(value), 500)


def _build_evidence_package(
    product: Product,
    researched_evidences: list[ResearchEvidence],
    enriched: ProductEnrichmentResult,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    product_payload = _product_payload(product)
    registry: dict[str, dict[str, Any]] = {
        PACKING_EVIDENCE_ID: {
            "evidence_id": PACKING_EVIDENCE_ID,
            "type": "packing_list",
            "fields": {key: value for key, value in product_payload.items() if key != "evidence_id"},
        }
    }
    for index, evidence in enumerate(researched_evidences[:MAX_SEARCH_EVIDENCES], 1):
        evidence_id = f"SEARCH-{index:03d}"
        item = {
            "evidence_id": evidence_id,
            "type": "search_result",
            "url": evidence.url,
            "domain": evidence.domain,
            "title": _clean(evidence.title, 500),
            "snippet": _clean(evidence.snippet, 1_000),
            "source_category": evidence.source_category,
            "strength": evidence.evidence_strength,
            "matched_reasons": evidence.relevance_reasons[:8],
        }
        entries.append(item)
        registry[evidence_id] = item
    web_entries: list[dict[str, Any]] = []
    for index, evidence in enumerate((item for item in enriched.fetches if item.fetch_status == "OK"), 1):
        evidence_id = f"WEB-{index:03d}"
        item = {
            "evidence_id": evidence_id,
            "type": "fetched_page",
            "url": evidence.final_url,
            "domain": evidence.domain,
            "title": _clean(evidence.title, 500),
            "text_excerpt": _clean(evidence.text_excerpt, MAX_EXCERPT_CHARS),
            "structured_data": _compact_structured_data(evidence.structured_data),
            "matched_signals": evidence.matched_signals[:12],
            "conflicts": [conflict.model_dump(mode="json") for conflict in evidence.conflicts],
            "content_hash": evidence.content_hash,
        }
        web_entries.append(item)
        registry[evidence_id] = item
    package = {
        "product": product_payload,
        "search_evidence": entries,
        "web_evidence": web_entries,
    }
    return package, registry


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise AnalysisValidationError("a resposta não é um objeto JSON")
    return value


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(
        r"\s+", " ", "".join(char for char in normalized if not unicodedata.combining(char))
    ).strip()


def _entry_contains(entry: dict[str, Any], value: str) -> bool:
    def scalar_values(item: Any) -> list[str]:
        if isinstance(item, dict):
            return [text for child in item.values() for text in scalar_values(child)]
        if isinstance(item, list):
            return [text for child in item for text in scalar_values(child)]
        return [str(item)] if item is not None else []

    haystack = _fold(" ".join(scalar_values(entry)))
    needle = _fold(value)
    return bool(needle) and needle in haystack


def _validate_grounding(
    analysis: LlmEvidenceAnalysis,
    registry: dict[str, dict[str, Any]],
    enriched: ProductEnrichmentResult,
) -> LlmEvidenceAnalysis:
    valid_ids = set(registry)
    used_ids = set(analysis.evidence_used)
    referenced = used_ids.copy()
    for field in analysis.confirmed_fields:
        referenced.update(field.evidence_ids)
    for conflict in analysis.conflicts:
        referenced.update(conflict.evidence_ids)
    invalid = sorted(referenced - valid_ids)
    if invalid:
        raise AnalysisValidationError(f"evidence_ids inexistentes: {', '.join(invalid)}")
    if any(not set(field.evidence_ids) <= used_ids for field in analysis.confirmed_fields):
        raise AnalysisValidationError("confirmed_fields deve usar IDs presentes em evidence_used")
    if any(not set(conflict.evidence_ids) <= used_ids for conflict in analysis.conflicts):
        raise AnalysisValidationError("conflicts deve usar IDs presentes em evidence_used")

    for confirmed in analysis.confirmed_fields:
        if not any(_entry_contains(registry[evidence_id], confirmed.value) for evidence_id in confirmed.evidence_ids):
            raise AnalysisValidationError(f"valor confirmado sem suporte: {confirmed.field}")

    deterministic_conflicts = [
        (conflict, evidence)
        for evidence in enriched.fetches
        for conflict in evidence.conflicts
        if evidence.fetch_status == "OK"
    ]
    deterministic_fields = {conflict.field for conflict, _ in deterministic_conflicts}
    returned_fields = {conflict.field for conflict in analysis.conflicts}
    if deterministic_fields - returned_fields:
        raise AnalysisValidationError("conflito conhecido foi omitido")
    if deterministic_conflicts and analysis.decision != "REVIEW":
        raise AnalysisValidationError("produto com conflito deve retornar REVIEW")

    product_fields = registry[PACKING_EVIDENCE_ID]["fields"]
    for conflict in analysis.conflicts:
        spreadsheet_value = product_fields.get(conflict.field)
        if not spreadsheet_value or _fold(conflict.spreadsheet_value) != _fold(spreadsheet_value):
            raise AnalysisValidationError(f"valor da planilha inválido no conflito: {conflict.field}")
        web_ids = [evidence_id for evidence_id in conflict.evidence_ids if evidence_id.startswith("WEB-")]
        if PACKING_EVIDENCE_ID not in conflict.evidence_ids or not web_ids:
            raise AnalysisValidationError("conflito deve citar Packing List e evidência web")
        for value in conflict.web_values:
            if not any(_entry_contains(registry[evidence_id], value) for evidence_id in web_ids):
                raise AnalysisValidationError(f"valor web sem suporte no conflito: {conflict.field}")

    confirmed_fields = {item.field for item in analysis.confirmed_fields}
    conflict_fields = {item.field for item in analysis.conflicts}
    unknown_fields = set(analysis.unknown_fields)
    if confirmed_fields & conflict_fields or confirmed_fields & unknown_fields or conflict_fields & unknown_fields:
        raise AnalysisValidationError("campos confirmados, conflitantes e desconhecidos devem ser distintos")
    expected_unknown = set(PRODUCT_FIELDS) - confirmed_fields - conflict_fields
    if not unknown_fields <= expected_unknown:
        raise AnalysisValidationError("unknown_fields contém campo já confirmado ou conflitante")
    if unknown_fields != expected_unknown:
        analysis = analysis.model_copy(update={
            "unknown_fields": [field for field in PRODUCT_FIELDS if field in expected_unknown],
        })
    if analysis.decision == "FOUND" and not analysis.product_match:
        raise AnalysisValidationError("FOUND exige product_match=true")
    if analysis.decision == "NOT_FOUND" and (analysis.product_match or analysis.confirmed_fields):
        raise AnalysisValidationError("NOT_FOUND não pode confirmar correspondência ou campos")
    return analysis


def _found_is_supported(package: dict[str, Any]) -> bool:
    web = package["web_evidence"]
    corroborating = [item for item in web if "code" in item["matched_signals"] and set(item["matched_signals"]) & {"item_name", "manufacturer", "brand"}]
    domains = {item["domain"] for item in corroborating}
    manufacturer_search = any(
        item["source_category"] == "MANUFACTURER" and item["strength"] == "STRONG"
        for item in package["search_evidence"]
    )
    return len(domains) >= 2 or (manufacturer_search and bool(corroborating))


def _calibrate_confidence(
    analysis: LlmEvidenceAnalysis,
    package: dict[str, Any],
) -> LlmEvidenceAnalysis:
    if analysis.decision == "FOUND":
        confidence = "HIGH" if _found_is_supported(package) else "LOW"
    elif analysis.decision == "REVIEW":
        confidence = "MEDIUM" if package["web_evidence"] else "LOW"
    else:
        confidence = "LOW"
    return analysis.model_copy(update={"confidence": confidence})


def _controlled_review(
    product: Product,
    *,
    prompt_version: str,
    evidence_count: int,
    input_chars: int,
    llm_used: bool,
    llm_error: str,
    latency_ms: int = 0,
    model_used: str | None = None,
    cache_status: str = "MISS",
) -> ProductAnalysisResult:
    return ProductAnalysisResult(
        product_id=product.product_id, code=product.code, decision="REVIEW", confidence="LOW",
        product_match=False, confirmed_fields=[], conflicts=[], unknown_fields=list(PRODUCT_FIELDS),
        reasoning_summary="A análise automática não pôde ser validada; revisão humana necessária.",
        evidence_used=[], warnings=["Análise de IA indisponível ou inválida."],
        llm_used=llm_used, llm_error=llm_error, model_used=model_used,
        latency_ms=latency_ms, prompt_version=prompt_version, analysis_version=ANALYSIS_VERSION,
        evidence_count=evidence_count, input_chars=input_chars, cache_status=cache_status,
    )


class EvidenceAnalysisService:
    def __init__(
        self,
        settings: Settings,
        gateway: OmniRouteService | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.cache = cache or AnalysisCache(
            settings.llm_analysis_cache_dir, settings.llm_analysis_cache_ttl_seconds
        )

    async def analyze(
        self,
        file_id: str,
        products: list[Product],
        enrichment: EnrichmentResponse,
        *,
        refresh_cache: bool,
    ) -> AnalysisResponse:
        researched_by_id = {item.product_id: item for item in enrichment.research.products}
        enriched_by_id = {item.product_id: item for item in enrichment.products}
        results: list[ProductAnalysisResult] = []
        llm_calls = hits = misses = 0
        for product in products:
            researched = researched_by_id[product.product_id]
            enriched = enriched_by_id[product.product_id]
            package, registry = _build_evidence_package(product, researched.evidences, enriched)
            if researched.status != "OK" or not researched.evidences:
                result = ProductAnalysisResult(
                    product_id=product.product_id, code=product.code, decision="NOT_FOUND",
                    confidence="LOW", product_match=False, confirmed_fields=[], conflicts=[],
                    unknown_fields=list(PRODUCT_FIELDS),
                    reasoning_summary="A pesquisa e o enriquecimento não produziram evidência válida para análise.",
                    evidence_used=[], warnings=[], llm_used=False, prompt_version=PROMPT_VERSION,
                    analysis_version=ANALYSIS_VERSION, evidence_count=len(registry), input_chars=0,
                    cache_status="SKIP",
                )
                results.append(result)
                logger.info(
                    "evidence_analysis file_id=%s product=%s llm_used=false prompt=%s evidence_count=%s input_chars=0 model=none latency_ms=0 decision=NOT_FOUND confidence=LOW cache=SKIP",
                    file_id, product.code or product.product_id, PROMPT_VERSION, len(registry),
                )
                continue

            serialized = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(serialized) > self.settings.llm_analysis_max_input_chars:
                # Limits above normally keep the payload below the cap; fail closed if they do not.
                results.append(_controlled_review(
                    product, prompt_version=PROMPT_VERSION, evidence_count=len(registry),
                    input_chars=len(serialized), llm_used=False, llm_error="INPUT_TOO_LARGE",
                    cache_status="SKIP",
                ))
                logger.warning(
                    "evidence_analysis file_id=%s product=%s llm_used=false prompt=%s evidence_count=%s input_chars=%s llm_error=INPUT_TOO_LARGE cache=SKIP",
                    file_id, product.code or product.product_id, PROMPT_VERSION, len(registry), len(serialized),
                )
                continue
            identity = {
                "analysis_version": ANALYSIS_VERSION, "prompt_version": PROMPT_VERSION,
                "product": package["product"],
                "evidence_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            }
            cache_key = self.cache.key(identity)
            cached = None if refresh_cache else self.cache.get(cache_key)
            if cached:
                result = ProductAnalysisResult.model_validate(cached)
                results.append(result.model_copy(update={"cache_status": "HIT", "llm_used": False}))
                hits += 1
                logger.info(
                    "evidence_analysis file_id=%s product=%s llm_used=false prompt=%s evidence_count=%s input_chars=%s model=%s latency_ms=0 decision=%s confidence=%s cache=HIT",
                    file_id, product.code or product.product_id, PROMPT_VERSION, len(registry),
                    len(serialized), result.model_used or "unknown", result.decision, result.confidence,
                )
                continue
            misses += 1
            messages = [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": serialized},
            ]
            completion_model = None
            latency_ms = 0
            try:
                validated = None
                last_error = "INVALID_JSON"
                for attempt in range(2):
                    async with _LLM_SEMAPHORE:
                        completion = await self.gateway.complete_json(
                            messages, timeout_seconds=self.settings.llm_analysis_timeout_seconds
                        )
                    llm_calls += 1
                    completion_model = completion.model
                    latency_ms += completion.latency_ms
                    try:
                        parsed = LlmEvidenceAnalysis.model_validate(_parse_json(completion.content))
                        validated = _validate_grounding(parsed, registry, enriched)
                        break
                    except (json.JSONDecodeError, ValidationError, AnalysisValidationError) as exc:
                        last_error = type(exc).__name__
                        if attempt == 0:
                            messages.append({"role": "assistant", "content": completion.content[:4_000]})
                            messages.append({
                                "role": "user",
                                "content": (
                                    "Sua resposta foi inválida. Retorne somente JSON compatível com o schema, "
                                    "preserve conflitos e use apenas evidence_ids fornecidos. Os únicos nomes "
                                    "de campo permitidos são: " + ", ".join(PRODUCT_FIELDS) + "."
                                ),
                            })
                if validated is None:
                    results.append(_controlled_review(
                        product, prompt_version=PROMPT_VERSION, evidence_count=len(registry),
                        input_chars=len(serialized), llm_used=True, llm_error=last_error,
                        latency_ms=latency_ms, model_used=completion_model,
                    ))
                    continue
                if validated.decision == "FOUND" and not _found_is_supported(package):
                    validated = validated.model_copy(update={
                        "decision": "REVIEW", "confidence": "LOW", "product_match": False,
                        "warnings": validated.warnings + ["FOUND rebaixado: corroboração insuficiente."],
                    })
                validated = _calibrate_confidence(validated, package)
                result = ProductAnalysisResult(
                    **validated.model_dump(), product_id=product.product_id, code=product.code,
                    llm_used=True, model_used=completion_model, latency_ms=latency_ms,
                    prompt_version=PROMPT_VERSION, analysis_version=ANALYSIS_VERSION,
                    evidence_count=len(registry), input_chars=len(serialized), cache_status="MISS",
                )
                self.cache.put(cache_key, result.model_dump(mode="json"))
                results.append(result)
                logger.info(
                    "evidence_analysis file_id=%s product=%s llm_used=true prompt=%s evidence_count=%s input_chars=%s model=%s latency_ms=%s decision=%s confidence=%s cache=MISS",
                    file_id, product.code or product.product_id, PROMPT_VERSION, len(registry),
                    len(serialized), completion_model or "unknown", latency_ms,
                    result.decision, result.confidence,
                )
            except OmniRouteError as exc:
                llm_calls += 1
                logger.warning(
                    "evidence_analysis file_id=%s product=%s llm_used=true prompt=%s evidence_count=%s input_chars=%s llm_error=%s cache=MISS",
                    file_id, product.code or product.product_id, PROMPT_VERSION, len(registry),
                    len(serialized), exc.status_code,
                )
                results.append(_controlled_review(
                    product, prompt_version=PROMPT_VERSION, evidence_count=len(registry),
                    input_chars=len(serialized), llm_used=True, llm_error="LLM_UNAVAILABLE",
                    latency_ms=latency_ms, model_used=completion_model,
                ))
        return AnalysisResponse(
            file_id=file_id, products=results, llm_calls=llm_calls,
            cache_hits=hits, cache_misses=misses,
            llm_used=any(item.llm_used for item in results),
        )
