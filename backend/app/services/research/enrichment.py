from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.services.research.fetch_cache import FetchCache
from app.services.research.fetcher import ControlledFetcher
from app.services.research.schemas import (
    EnrichedWebEvidence,
    EnrichmentResponse,
    EvidenceConflict,
    ProductEnrichmentResult,
    ResearchResponse,
    SourceFact,
)
from app.services.spreadsheets.schemas import Product


MATCH_FIELDS = (
    "code", "item_name", "manufacturer", "brand", "composition", "construction", "ncm",
)
WEB_FIELD_MAP = {
    "sku": "code", "mpn": "code", "model": "code", "name": "item_name",
    "manufacturer": "manufacturer", "brand": "brand", "material": "composition",
    "color": "color", "category": "item_name",
}


def _fold(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").casefold())
    return re.sub(r"\s+", " ", "".join(char for char in normalized if not unicodedata.combining(char))).strip()


def _compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9%]", "", _fold(value))


def _structured_items(evidence: EnrichedWebEvidence) -> list[dict[str, Any]]:
    items = evidence.structured_data.get("items", [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def apply_product_matching(evidence: EnrichedWebEvidence, product: Product) -> EnrichedWebEvidence:
    result = evidence.model_copy(deep=True)
    if result.fetch_status != "OK":
        return result
    text = " ".join(filter(None, [
        result.title, result.meta_description, *result.headings, result.text_excerpt,
    ]))
    for item in _structured_items(result):
        text += " " + " ".join(str(value) for value in item.values())
    folded_text = _fold(text)
    compact_text = _compact(text)

    for field in MATCH_FIELDS:
        value = getattr(product, field)
        if not value:
            continue
        folded_value = _fold(value)
        compact_value = _compact(value)
        matched = bool(
            (len(folded_value) >= 3 and folded_value in folded_text)
            or (len(compact_value) >= 4 and compact_value in compact_text)
        )
        (result.matched_signals if matched else result.missing_signals).append(field)

    spreadsheet_facts = [
        SourceFact(
            field=field,
            value=str(value),
            source_type="spreadsheet",
            source="packing_list",
        )
        for field in (*MATCH_FIELDS, "color")
        if (value := getattr(product, field, None))
    ]
    web_facts: list[SourceFact] = []
    for item in _structured_items(result):
        for json_field, product_field in WEB_FIELD_MAP.items():
            value = item.get(json_field)
            values = value if isinstance(value, list) else [value]
            for candidate in values:
                cleaned = re.sub(r"\s+", " ", str(candidate or "")).strip()[:2000]
                if cleaned and not any(f.field == product_field and f.value == cleaned for f in web_facts):
                    web_facts.append(SourceFact(
                        field=product_field,
                        value=cleaned,
                        source_type="web",
                        source_url=result.final_url,
                    ))
    result.source_facts = spreadsheet_facts + web_facts
    for web_fact in web_facts:
        spreadsheet_value = getattr(product, web_fact.field, None)
        if not spreadsheet_value:
            continue
        spreadsheet_compact = _compact(str(spreadsheet_value))
        web_compact = _compact(web_fact.value)
        if not spreadsheet_compact or not web_compact:
            continue
        if spreadsheet_compact in web_compact or web_compact in spreadsheet_compact:
            continue
        if web_fact.field not in {"composition", "color", "manufacturer", "brand", "code"}:
            continue
        result.conflicts.append(EvidenceConflict(
            field=web_fact.field,
            spreadsheet=SourceFact(
                field=web_fact.field,
                value=str(spreadsheet_value),
                source_type="spreadsheet",
                source="packing_list",
            ),
            web=web_fact,
        ))
    return result


class EvidenceEnrichmentService:
    def __init__(self, settings: Settings, fetcher: ControlledFetcher | None = None) -> None:
        self.settings = settings
        self.fetcher = fetcher or ControlledFetcher(
            cache=FetchCache(settings.fetch_cache_dir, settings.fetch_cache_ttl_seconds),
            timeout_seconds=settings.fetch_timeout_seconds,
            max_bytes=settings.fetch_max_bytes,
        )

    async def enrich(
        self,
        file_id: str,
        products: list[Product],
        research: ResearchResponse,
        *,
        max_pages_per_product: int,
        refresh_fetch_cache: bool,
    ) -> EnrichmentResponse:
        by_id = {product.product_id: product for product in products}
        results: list[ProductEnrichmentResult] = []
        fetch_requests = hits = misses = expired = 0
        for researched in research.products:
            product = by_id[researched.product_id]
            approved = [
                evidence for evidence in researched.evidences
                if evidence.evidence_strength in {"STRONG", "MODERATE"}
            ][:max_pages_per_product]
            fetches: list[EnrichedWebEvidence] = []
            for evidence in approved:
                fetched = await self.fetcher.fetch(evidence.url, refresh_cache=refresh_fetch_cache)
                if fetched.cache_status == "HIT":
                    hits += 1
                elif fetched.cache_status == "EXPIRED":
                    expired += 1
                    fetch_requests += 1
                else:
                    misses += 1
                    fetch_requests += 1
                fetches.append(apply_product_matching(fetched, product))
            results.append(ProductEnrichmentResult(
                product_id=product.product_id,
                code=product.code,
                search_status=researched.status,
                approved_urls=len(approved),
                fetches=fetches,
            ))
        return EnrichmentResponse(
            file_id=file_id,
            provider=research.provider,
            researched_at=datetime.now(UTC),
            research=research,
            products=results,
            fetch_requests=fetch_requests,
            fetch_cache_hits=hits,
            fetch_cache_misses=misses,
            fetch_cache_expired=expired,
            llm_used=False,
        )
