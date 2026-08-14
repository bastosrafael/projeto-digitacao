from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.research.label_schemas import HangtagEvidence, WashLabelEvidence
from app.services.research.multimodal_schemas import VisualEvidence

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
InternalSupport = Literal["STRONG", "MODERATE", "WEAK", "NONE"]
ExternalSupport = Literal["STRONG", "LIMITED", "NONE"]
LabelField = Literal[
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories", "category_visual", "primary_color", "sleeves",
    "straps", "length", "visible_details", "country_of_origin", "material",
    "style_code_from_label", "sku_from_label", "barcode_text",
]


class LabelsConfirmedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    source_types: list[str] = Field(default_factory=list, max_length=8)


class LabelsConflictSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    evidence_type: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=1000)


class LabelsConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=60)
    sources: list[LabelsConflictSource] = Field(min_length=2, max_length=8)


class LlmLabelsCrossAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["FOUND", "REVIEW", "NOT_FOUND"]
    confidence: Confidence
    internal_support: InternalSupport
    external_support: ExternalSupport
    confirmed_fields: list[LabelsConfirmedField] = Field(default_factory=list, max_length=30)
    conflicts: list[LabelsConflict] = Field(default_factory=list, max_length=20)
    unknown_fields: list[str] = Field(default_factory=list, max_length=40)
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    evidence_used: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class LabelStatusEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: str
    image_type: str
    status: str
    error: str | None = None


class ProductLabelsMultimodalResult(LlmLabelsCrossAnalysis):
    product_id: str
    code: str | None = None
    product_image_used: bool
    wash_label_used: bool
    hangtag_used: bool
    visual_evidence: VisualEvidence | None = None
    wash_label_evidence: WashLabelEvidence | None = None
    hangtag_evidence: HangtagEvidence | None = None
    label_statuses: list[LabelStatusEntry] = Field(default_factory=list, max_length=5)
    llm_used_visual: bool = False
    llm_used_wash: bool = False
    llm_used_hangtag: bool = False
    llm_used_text: bool = False
    visual_error: str | None = None
    wash_error: str | None = None
    hangtag_error: str | None = None
    llm_error: str | None = None
    textual_model: str | None = None
    textual_latency_ms: int = 0
    prompt_version: str
    analysis_version: str
    evidence_count: int = 0
    input_chars: int = 0
    cache_status: Literal["HIT", "MISS"]


class LabelsMultimodalResponse(BaseModel):
    file_id: str
    products: list[ProductLabelsMultimodalResult]
    visual_llm_calls: int = 0
    wash_llm_calls: int = 0
    hangtag_llm_calls: int = 0
    textual_llm_calls: int = 0
    visual_cache_hits: int = 0
    wash_cache_hits: int = 0
    hangtag_cache_hits: int = 0
    labels_cache_hits: int = 0
    labels_cache_misses: int = 0
    llm_used_visual: bool = False
    llm_used_wash: bool = False
    llm_used_hangtag: bool = False
    llm_used_text: bool = False


class LabelsMultimodalRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=2)
    max_queries_per_product: int = Field(default=3, ge=1, le=4)
    max_results_per_query: int = Field(default=8, ge=1, le=10)
    max_pages_per_product: int = Field(default=3, ge=1, le=3)
    refresh_cache: bool = False
    refresh_fetch_cache: bool = False
    refresh_visual_cache: bool = False
    refresh_multimodal_cache: bool = False
    refresh_wash_cache: bool = False
    refresh_hangtag_cache: bool = False
    refresh_labels_cache: bool = False
