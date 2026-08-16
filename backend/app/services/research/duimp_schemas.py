"""Schemas Pydantic para a Fase 8A — gerador de descrição técnica DUIMP."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FactEntry(BaseModel):
    """Um fato individual no Fact Ledger."""

    model_config = {"extra": "forbid"}

    value: Any
    status: str  # CONFIRMED | CONFLICTING | UNKNOWN | UNCERTAIN
    evidence_ids: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)


class CompositionLayer(BaseModel):
    """Uma camada de composição (exterior, interior/forro)."""

    model_config = {"extra": "forbid"}

    layer_name: str  # "exterior", "interior", "lining"
    fibers: list[dict[str, Any]]
    status: str
    evidence_ids: list[str] = Field(default_factory=list)


class FactLedger(BaseModel):
    """Ledger determinístico de fatos para geração DUIMP."""

    model_config = {"extra": "forbid"}

    product_code: FactEntry
    item_name: FactEntry
    category: FactEntry
    ncm: FactEntry
    construction: FactEntry
    manufacturer: FactEntry
    brand: FactEntry
    country_of_origin: FactEntry
    size: FactEntry
    primary_color: FactEntry
    sleeves: FactEntry
    straps: FactEntry
    length: FactEntry
    visible_details: FactEntry
    composition_layers: list[CompositionLayer]
    composition_status: str  # overall status for composition
    composition_evidence_ids: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """Claim rastreável na descrição gerada."""

    model_config = {"extra": "forbid"}

    claim_id: str
    field: str
    value: str
    evidence_ids: list[str]


class ExcludedField(BaseModel):
    """Campo excluído da descrição com motivo."""

    model_config = {"extra": "forbid"}

    field: str
    reason: str  # UNKNOWN | UNCERTAIN | CONFLICTING


class LlmDuimpDescription(BaseModel):
    """Saída esperada do LLM para a descrição DUIMP."""

    model_config = {"extra": "forbid"}

    description: str
    claims: list[Claim]


class DuimpConflict(BaseModel):
    """Conflito preservado no resultado."""

    model_config = {"extra": "forbid"}

    field: str
    sources: list[dict[str, str]]


class DuimpDescriptionResult(BaseModel):
    """Resultado final da Fase 8A."""

    model_config = {"extra": "forbid"}

    product_code: str
    description: str
    status: str  # GENERATED | REVIEW_REQUIRED | INSUFFICIENT_EVIDENCE | ERROR
    confidence: str  # HIGH | MEDIUM | LOW
    claims: list[Claim]
    excluded_fields: list[ExcludedField]
    conflicts: list[DuimpConflict]
    warnings: list[str]
    prompt_version: str
    generator_version: str
    model: str | None = None
    latency_ms: int = 0
    llm_used: bool = False
    cache_status: str = "MISS"


class DuimpGenerateRequest(BaseModel):
    """Requisição para o endpoint de geração DUIMP."""

    model_config = {"extra": "forbid"}

    product_id: str
