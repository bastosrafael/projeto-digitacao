from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceField = Literal[
    "code", "item_name", "ncm", "composition", "construction", "manufacturer",
    "supplier", "brand", "color", "size", "purpose", "dimensions", "weight",
    "capacity", "voltage", "power", "frequency", "battery", "recharge",
    "connection", "accessories",
]


class ConfirmedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: EvidenceField
    value: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class AnalysisConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: EvidenceField
    spreadsheet_value: str = Field(min_length=1, max_length=1000)
    web_values: list[str] = Field(min_length=1, max_length=6)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class LlmEvidenceAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["FOUND", "REVIEW", "NOT_FOUND"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    product_match: bool
    confirmed_fields: list[ConfirmedField] = Field(default_factory=list, max_length=20)
    conflicts: list[AnalysisConflict] = Field(default_factory=list, max_length=20)
    unknown_fields: list[EvidenceField] = Field(default_factory=list, max_length=30)
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    evidence_used: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ProductAnalysisResult(LlmEvidenceAnalysis):
    product_id: str
    code: str | None = None
    llm_used: bool
    llm_error: str | None = None
    model_used: str | None = None
    latency_ms: int = 0
    prompt_version: str
    analysis_version: str
    evidence_count: int = 0
    input_chars: int = 0
    cache_status: Literal["HIT", "MISS", "SKIP"]


class AnalysisResponse(BaseModel):
    file_id: str
    products: list[ProductAnalysisResult]
    llm_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    llm_used: bool = False


class AnalysisRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=3)
    max_queries_per_product: int = Field(default=3, ge=1, le=4)
    max_results_per_query: int = Field(default=8, ge=1, le=10)
    max_pages_per_product: int = Field(default=3, ge=1, le=3)
    refresh_cache: bool = False
    refresh_fetch_cache: bool = False
    refresh_analysis_cache: bool = False
