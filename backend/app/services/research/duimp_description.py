"""Serviço de geração de descrição técnica DUIMP — Fase 8A.

Fluxo: evidências → fact ledger → claims permitidos → LLM → validação → descrição.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.duimp_schemas import (
    Claim,
    DuimpConflict,
    DuimpDescriptionResult,
    DuimpGenerateRequest,
    ExcludedField,
    LlmDuimpDescription,
)
from app.services.research.fact_ledger import (
    build_fact_ledger,
    get_confirmed_facts_summary,
    get_excluded_fields,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "duimp-description-v1"
GENERATOR_VERSION = "duimp-generator-v2"

_ESSENTIAL_FIELDS = {"category", "item_name"}
_SUPPORTING_FIELDS = {"composition", "construction"}

_DUIMP_SEMAPHORE = asyncio.Semaphore(1)


def _load_prompt() -> str:
    return files("app.prompts").joinpath("duimp_description_v1.txt").read_text(encoding="utf-8")


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    return json.loads(cleaned)


def _validate_claims(
    llm_output: LlmDuimpDescription,
    confirmed_facts: dict[str, Any],
) -> list[str]:
    """Valida se todos os claims apontam para fatos CONFIRMED permitidos.

    Retorna lista de violações. Lista vazia = válido.
    """
    violations: list[str] = []
    allowed_fields = set(confirmed_facts.keys())

    for claim in llm_output.claims:
        if claim.field not in allowed_fields:
            violations.append(
                f"Claim {claim.claim_id}: field '{claim.field}' not in confirmed facts"
            )
        # Verify evidence_ids are non-empty
        if not claim.evidence_ids:
            violations.append(
                f"Claim {claim.claim_id}: empty evidence_ids"
            )

    return violations


def _compute_confidence(
    confirmed_count: int,
    excluded_count: int,
    conflict_count: int,
    has_composition: bool,
) -> str:
    """Calcula confidence deterministicamente."""
    if conflict_count > 0:
        return "MEDIUM"
    if confirmed_count >= 6 and has_composition:
        return "HIGH"
    if confirmed_count >= 4:
        return "MEDIUM"
    return "LOW"


def _build_conflicts(labels_result: dict[str, Any]) -> list[DuimpConflict]:
    conflicts: list[DuimpConflict] = []
    for c in labels_result.get("conflicts", []):
        conflicts.append(DuimpConflict(
            field=c["field"],
            sources=c.get("sources", []),
        ))
    return conflicts


def check_sufficiency(
    confirmed_facts: dict[str, Any],
    conflict_fields: set[str],
) -> tuple[bool, str]:
    """Gate determinístico: avalia se há evidência suficiente para gerar descrição.

    Retorna (sufficient, reason).
    NCM sozinho NÃO é suficiente.
    Precisa de pelo menos 1 essencial (category ou item_name) + 1 suporte (composition ou construction).
    Conflito em campo essencial (category/item_name) bloqueia.
    Conflito em campo de suporte (composition/construction) NÃO bloqueia — tratado via confidence.
    """
    if not confirmed_facts:
        return False, "no confirmed facts"

    has_essential = bool(_ESSENTIAL_FIELDS & set(confirmed_facts.keys()))
    has_supporting = bool(_SUPPORTING_FIELDS & set(confirmed_facts.keys()))

    if not has_essential:
        return False, "no category or item_name confirmed"

    if not has_supporting:
        return False, "no composition or construction confirmed"

    # Conflito direto em campo essencial bloqueia
    essential_in_conflict = _ESSENTIAL_FIELDS & conflict_fields
    if essential_in_conflict:
        return False, f"conflict in essential field(s): {', '.join(sorted(essential_in_conflict))}"

    return True, "sufficient evidence"


class DuimpDescriptionService:
    def __init__(
        self,
        settings: Settings,
        gateway: OmniRouteService | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.cache = cache or AnalysisCache(
            settings.duimp_description_cache_dir,
            settings.duimp_description_cache_ttl_seconds,
        )

    async def generate(
        self,
        labels_result: dict[str, Any],
        wash_evidence: dict[str, Any] | None = None,
        hangtag_evidence: dict[str, Any] | None = None,
        visual_evidence: dict[str, Any] | None = None,
        *,
        refresh_cache: bool = False,
        packing_fallback: bool = False,
    ) -> DuimpDescriptionResult:
        product_code = labels_result.get("code") or labels_result.get("product_id", "UNKNOWN")

        # Build fact ledger deterministically
        ledger = build_fact_ledger(
            labels_result, wash_evidence, hangtag_evidence, visual_evidence
        )
        confirmed_facts = get_confirmed_facts_summary(ledger)
        excluded_fields = get_excluded_fields(ledger)
        conflicts = _build_conflicts(labels_result)

        # Gate determinístico de suficiência
        conflict_fields_set = {c.field for c in conflicts}
        sufficient, sufficiency_reason = check_sufficiency(
            confirmed_facts, conflict_fields_set
        )
        if not sufficient:
            return DuimpDescriptionResult(
                product_code=product_code,
                description="",
                status="INSUFFICIENT_EVIDENCE",
                confidence="LOW",
                claims=[],
                excluded_fields=excluded_fields,
                conflicts=conflicts,
                warnings=[f"Insufficient evidence: {sufficiency_reason}"],
                prompt_version=PROMPT_VERSION,
                generator_version=GENERATOR_VERSION,
                llm_used=False,
                sufficiency_reason=sufficiency_reason,
            )

        # Build cache key
        facts_hash = hashlib.sha256(
            json.dumps(confirmed_facts, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        identity = {
            "generator_version": GENERATOR_VERSION,
            "product_code": product_code,
            "facts_hash": facts_hash,
            "prompt_version": PROMPT_VERSION,
        }
        cache_key = self.cache.key(identity)

        # Check cache
        cached = None if refresh_cache else self.cache.get(cache_key)
        if cached:
            result = DuimpDescriptionResult.model_validate(cached)
            logger.info(
                "duimp_description code=%s cache=HIT llm_used=false",
                product_code,
            )
            return result.model_copy(update={"cache_status": "HIT", "llm_used": False, "latency_ms": 0})

        # Build prompt
        prompt_template = _load_prompt()
        prompt = prompt_template.replace(
            "{{confirmed_facts}}",
            json.dumps(confirmed_facts, indent=2, ensure_ascii=False),
        ).replace(
            "{{excluded_fields}}",
            json.dumps(
                [{"field": e.field, "reason": e.reason} for e in excluded_fields],
                ensure_ascii=False,
            ),
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": (
                f"Generate a technical product description for code {product_code} "
                "using ONLY the confirmed facts above. Return strict JSON."
            )},
        ]

        # LLM call with retry
        calls = 0
        latency = 0
        model = self.settings.omniroute_model
        validated: LlmDuimpDescription | None = None
        warnings: list[str] = []

        for attempt in range(2):
            try:
                async with _DUIMP_SEMAPHORE:
                    completion = await self.gateway.complete_json(
                        messages,
                        timeout_seconds=self.settings.duimp_description_timeout_seconds,
                    )
                calls += 1
                latency += completion.latency_ms
                model = completion.model or model

                parsed = _parse_json(completion.content)
                validated = LlmDuimpDescription.model_validate(parsed)

                # Validate claims against confirmed facts
                violations = _validate_claims(validated, confirmed_facts)
                if violations:
                    warnings.extend(violations)
                    if attempt == 0:
                        messages.append({"role": "user", "content": (
                            "The previous response contained unauthorized claims:\n"
                            + "\n".join(f"- {v}" for v in violations)
                            + "\n\nRegenerate using ONLY confirmed facts. "
                            "Remove any claim whose field is not in CONFIRMED_FACTS."
                        )})
                        validated = None
                        continue
                    else:
                        # Second failure
                        return DuimpDescriptionResult(
                            product_code=product_code,
                            description="",
                            status="REVIEW_REQUIRED",
                            confidence="LOW",
                            claims=[],
                            excluded_fields=excluded_fields,
                            conflicts=conflicts,
                            warnings=warnings + ["LLM produced unauthorized claims on retry."],
                            prompt_version=PROMPT_VERSION,
                            generator_version=GENERATOR_VERSION,
                            model=model,
                            latency_ms=latency,
                            llm_used=True,
                            cache_status="MISS",
                        )
                break

            except OmniRouteError:
                calls += 1
                raise
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                warnings.append(f"Attempt {attempt + 1}: {type(exc).__name__}")
                if attempt == 0:
                    messages.append({"role": "user", "content": (
                        "The previous output was invalid JSON or violated the schema. "
                        "Return ONLY valid JSON matching the required format."
                    )})
                    continue

        if validated is None:
            return DuimpDescriptionResult(
                product_code=product_code,
                description="",
                status="REVIEW_REQUIRED",
                confidence="LOW",
                claims=[],
                excluded_fields=excluded_fields,
                conflicts=conflicts,
                warnings=warnings + ["LLM failed to produce valid description after retry."],
                prompt_version=PROMPT_VERSION,
                generator_version=GENERATOR_VERSION,
                model=model,
                latency_ms=latency,
                llm_used=True,
                cache_status="MISS",
            )

        # Compute confidence
        confidence = _compute_confidence(
            confirmed_count=len(confirmed_facts),
            excluded_count=len(excluded_fields),
            conflict_count=len(conflicts),
            has_composition="composition" in confirmed_facts,
        )

        result = DuimpDescriptionResult(
            product_code=product_code,
            description=validated.description,
            status="GENERATED",
            confidence=confidence,
            claims=validated.claims,
            excluded_fields=excluded_fields,
            conflicts=conflicts,
            warnings=warnings,
            prompt_version=PROMPT_VERSION,
            generator_version=GENERATOR_VERSION,
            model=model,
            latency_ms=latency,
            llm_used=True,
            cache_status="MISS",
            packing_fallback=packing_fallback,
            sufficiency_reason="sufficient evidence",
        )

        self.cache.put(cache_key, result.model_dump(mode="json"))
        logger.info(
            "duimp_description code=%s status=%s confidence=%s model=%s latency_ms=%s llm_used=true cache=MISS claims=%s excluded=%s conflicts=%s",
            product_code, result.status, confidence, model, latency,
            len(result.claims), len(excluded_fields), len(conflicts),
        )
        return result
