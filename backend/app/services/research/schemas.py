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
