from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
VisualField = Literal["category_visual", "primary_color", "sleeves", "straps", "length"]
MultimodalField = Literal[
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories", "category_visual", "primary_color", "sleeves",
    "straps", "length", "visible_details",
]


class VisualAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=300)
    confidence: Confidence


class ObservableAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_visual: VisualAttribute
    primary_color: VisualAttribute
    sleeves: VisualAttribute
    straps: VisualAttribute
    length: VisualAttribute
    visible_details: list[VisualAttribute] = Field(default_factory=list, max_length=12)


class UncertainVisualAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: VisualField
    candidate_values: list[str] = Field(default_factory=list, max_length=5)
    reason: str = Field(min_length=1, max_length=500)


class LlmVisualAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observable_attributes: ObservableAttributes
    uncertain_attributes: list[UncertainVisualAttribute] = Field(default_factory=list, max_length=10)
    unknown_attributes: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class VisualEvidence(LlmVisualAttributes):
    evidence_id: str
    image_id: str
    image_type: Literal["PRODUCT_IMAGE"]
    product_code: str
    sheet: str
    anchor_row: int
    anchor_column: int
    image_sha256: str
    mime_type: Literal["image/jpeg", "image/png"]
    width: int
    height: int
    bytes: int
    original_width: int
    original_height: int
    original_bytes: int
    preprocessing_version: str
    request_size_bytes: int
    model: str
    prompt_version: str
    latency_ms: int = 0
    cache_status: Literal["HIT", "MISS"]
    llm_used: bool


class MultimodalConfirmedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: MultimodalField
    value: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class ConflictSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    value: str = Field(min_length=1, max_length=1000)


class MultimodalConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: MultimodalField
    sources: list[ConflictSource] = Field(min_length=2, max_length=8)


class LlmMultimodalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["FOUND", "REVIEW", "NOT_FOUND"]
    confidence: Confidence
    internal_visual_match: Literal["CONSISTENT", "UNCERTAIN", "CONFLICTING"]
    external_support: Literal["STRONG", "LIMITED", "NONE"]
    confirmed_fields: list[MultimodalConfirmedField] = Field(default_factory=list, max_length=25)
    conflicts: list[MultimodalConflict] = Field(default_factory=list, max_length=20)
    unknown_fields: list[MultimodalField] = Field(default_factory=list, max_length=35)
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    evidence_used: list[str] = Field(default_factory=list, max_length=25)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ProductMultimodalResult(LlmMultimodalAnalysis):
    product_id: str
    code: str | None = None
    visual_used: bool
    visual_evidence: VisualEvidence | None = None
    llm_used_visual: bool
    llm_used_text: bool
    visual_error: str | None = None
    llm_error: str | None = None
    textual_model: str | None = None
    textual_latency_ms: int = 0
    prompt_version: str
    analysis_version: str
    evidence_count: int = 0
    input_chars: int = 0
    cache_status: Literal["HIT", "MISS"]


class MultimodalResponse(BaseModel):
    file_id: str
    products: list[ProductMultimodalResult]
    visual_llm_calls: int = 0
    textual_llm_calls: int = 0
    visual_cache_hits: int = 0
    visual_cache_misses: int = 0
    multimodal_cache_hits: int = 0
    multimodal_cache_misses: int = 0
    llm_used_visual: bool = False
    llm_used_text: bool = False


class MultimodalRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=2)
    max_queries_per_product: int = Field(default=3, ge=1, le=4)
    max_results_per_query: int = Field(default=8, ge=1, le=10)
    max_pages_per_product: int = Field(default=3, ge=1, le=3)
    refresh_cache: bool = False
    refresh_fetch_cache: bool = False
    refresh_visual_cache: bool = False
    refresh_multimodal_cache: bool = False
