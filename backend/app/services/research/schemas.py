from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResearchEvidence(BaseModel):
    title: str
    url: str
    snippet: str = ""
    provider: str
    source_engine: str | None = None
    domain: str
    source_category: Literal["MANUFACTURER", "SUPPLIER", "DISTRIBUTOR", "STORE", "MARKETPLACE", "UNKNOWN"]
    evidence_strength: Literal["STRONG", "MODERATE", "WEAK"]
    position: int
    retrieved_at: datetime
    query: str
    score: float
    relevance_reasons: list[str]


class QueryExecution(BaseModel):
    query: str
    status: Literal["OK", "ERRO"]
    from_cache: bool
    provider: str
    cache_status: Literal["HIT", "MISS"]
    raw_results: int = 0
    deduplicated_results: int = 0
    filtered_results: int = 0
    discarded_results: int = 0
    discard_reasons: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class ProductResearchResult(BaseModel):
    product_id: str
    code: str | None = None
    status: Literal["OK", "NÃO_ENCONTRADO", "ERRO"]
    queries: list[QueryExecution]
    evidences: list[ResearchEvidence]
    raw_results: int = 0
    deduplicated_results: int = 0
    discarded_results: int = 0
    discard_reasons: dict[str, int] = Field(default_factory=dict)


class ResearchResponse(BaseModel):
    file_id: str
    provider: str
    researched_at: datetime
    products: list[ProductResearchResult]
    query_count: int
    gateway_calls: int
    cache_hits: int
    cache_misses: int
    llm_used: bool = False


class ResearchRequest(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=3)
    max_queries_per_product: int = Field(default=3, ge=1, le=4)
    max_results_per_query: int = Field(default=8, ge=1, le=10)
    refresh_cache: bool = False


class EnrichmentRequest(ResearchRequest):
    max_pages_per_product: int = Field(default=3, ge=1, le=3)
    refresh_fetch_cache: bool = False


class SourceFact(BaseModel):
    field: str
    value: str
    source_type: Literal["spreadsheet", "web"]
    source: str | None = None
    source_url: str | None = None


class EvidenceConflict(BaseModel):
    field: str
    spreadsheet: SourceFact
    web: SourceFact


class EnrichedWebEvidence(BaseModel):
    url: str
    final_url: str
    domain: str
    http_status: int | None = None
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    headings: list[str] = Field(default_factory=list)
    text_excerpt: str = ""
    structured_data: dict = Field(default_factory=dict)
    matched_signals: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    source_facts: list[SourceFact] = Field(default_factory=list)
    fetch_status: Literal[
        "OK", "BLOCKED", "TIMEOUT", "TOO_LARGE", "UNSUPPORTED_CONTENT",
        "HTTP_ERROR", "SSRF_BLOCKED", "PARSE_ERROR",
    ]
    fetched_at: datetime
    content_hash: str | None = None
    bytes_downloaded: int = 0
    elapsed_ms: int = 0
    cache_status: Literal["HIT", "MISS", "EXPIRED"] = "MISS"
    error: str | None = None


class ProductEnrichmentResult(BaseModel):
    product_id: str
    code: str | None = None
    search_status: Literal["OK", "NÃO_ENCONTRADO", "ERRO"]
    approved_urls: int = 0
    fetches: list[EnrichedWebEvidence] = Field(default_factory=list)


class EnrichmentResponse(BaseModel):
    file_id: str
    provider: str
    researched_at: datetime
    research: ResearchResponse
    products: list[ProductEnrichmentResult]
    fetch_requests: int = 0
    fetch_cache_hits: int = 0
    fetch_cache_misses: int = 0
    fetch_cache_expired: int = 0
    llm_used: bool = False
