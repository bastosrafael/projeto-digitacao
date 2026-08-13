from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.config import Settings
from app.services.omniroute import OmniRouteError, OmniRouteService
from app.services.research.cache import SearchCache
from app.services.research.filtering import evaluate_result
from app.services.research.schemas import (
    ProductResearchResult,
    QueryExecution,
    ResearchResponse,
)
from app.services.spreadsheets.schemas import Product

logger = logging.getLogger(__name__)


class ProductResearchService:
    def __init__(self, settings: Settings, gateway: OmniRouteService | None = None) -> None:
        self.settings = settings
        self.gateway = gateway or OmniRouteService(settings)
        self.cache = SearchCache(settings.search_cache_dir, settings.search_cache_ttl_seconds)

    async def research(
        self,
        file_id: str,
        products: list[Product],
        *,
        max_queries_per_product: int,
        max_results_per_query: int,
        refresh_cache: bool,
    ) -> ResearchResponse:
        results: list[ProductResearchResult] = []
        query_count = gateway_calls = cache_hits = cache_misses = 0

        # Intencionalmente sequencial: o HOMELAB tem pouca RAM e este piloto usa baixa concorrência.
        for product in products:
            executions: list[QueryExecution] = []
            evidences_by_url = {}
            raw_count = 0
            seen_urls: set[str] = set()
            product_discard_reasons: dict[str, int] = {}
            errors = 0
            queries = product.research_preparation.queries[:max_queries_per_product]
            for query in queries:
                query_count += 1
                payload = None if refresh_cache else self.cache.get(self.settings.search_provider, query)
                from_cache = payload is not None
                if from_cache:
                    cache_hits += 1
                else:
                    cache_misses += 1
                    try:
                        payload = await self.gateway.search(
                            query,
                            provider=self.settings.search_provider,
                            max_results=max_results_per_query,
                        )
                        gateway_calls += 1
                        try:
                            self.cache.put(self.settings.search_provider, query, payload)
                        except OSError as exc:
                            logger.warning("Não foi possível persistir o cache da pesquisa: %s", type(exc).__name__)
                    except OmniRouteError as exc:
                        errors += 1
                        executions.append(
                            QueryExecution(
                                query=query,
                                status="ERRO",
                                from_cache=False,
                                provider=self.settings.search_provider,
                                cache_status="MISS",
                                error=str(exc),
                            )
                        )
                        continue

                raw_results = payload.get("results", []) if isinstance(payload, dict) else []
                raw_count += len(raw_results)
                deduplicated = filtered = 0
                query_discard_reasons: dict[str, int] = {}

                def discard(reason: str) -> None:
                    query_discard_reasons[reason] = query_discard_reasons.get(reason, 0) + 1
                    product_discard_reasons[reason] = product_discard_reasons.get(reason, 0) + 1

                for raw in raw_results:
                    if not isinstance(raw, dict):
                        discard("invalid_result")
                        continue
                    evaluation = evaluate_result(raw, product, query, self.settings.search_provider)
                    if evaluation.canonical_url is None:
                        discard(evaluation.discard_reason or "invalid_result")
                        continue
                    if evaluation.canonical_url in seen_urls:
                        discard("duplicate_url")
                        continue
                    seen_urls.add(evaluation.canonical_url)
                    deduplicated += 1
                    if evaluation.evidence is None:
                        discard(evaluation.discard_reason or "filtered")
                        continue
                    evidences_by_url[evaluation.evidence.url] = evaluation.evidence
                    filtered += 1
                executions.append(
                    QueryExecution(
                        query=query,
                        status="OK",
                        from_cache=from_cache,
                        provider=self.settings.search_provider,
                        cache_status="HIT" if from_cache else "MISS",
                        raw_results=len(raw_results),
                        deduplicated_results=deduplicated,
                        filtered_results=filtered,
                        discarded_results=len(raw_results) - filtered,
                        discard_reasons=query_discard_reasons,
                    )
                )

            evidences = sorted(evidences_by_url.values(), key=lambda item: (-item.score, item.position))
            distinct_domains = {evidence.domain for evidence in evidences}
            if len(distinct_domains) >= 2:
                for evidence in evidences:
                    evidence.score = round(evidence.score + 0.5, 2)
                    evidence.relevance_reasons.append("corroboração em fontes de domínios distintos")
                evidences.sort(key=lambda item: (-item.score, item.position))
            if evidences:
                status = "OK"
            elif errors and errors == len(queries):
                status = "ERRO"
            else:
                status = "NÃO_ENCONTRADO"
            results.append(
                ProductResearchResult(
                    product_id=product.product_id,
                    code=product.code,
                    status=status,
                    queries=executions,
                    evidences=evidences,
                    raw_results=raw_count,
                    deduplicated_results=len(seen_urls),
                    discarded_results=max(0, raw_count - len(evidences_by_url)),
                    discard_reasons=product_discard_reasons,
                )
            )

        return ResearchResponse(
            file_id=file_id,
            provider=self.settings.search_provider,
            researched_at=datetime.now(UTC),
            products=results,
            query_count=query_count,
            gateway_calls=gateway_calls,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            llm_used=False,
        )
