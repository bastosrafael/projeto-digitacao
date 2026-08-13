import asyncio
import brotli
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.services.research import fetch_cache as fetch_cache_module
from app.services.research.enrichment import EvidenceEnrichmentService, apply_product_matching
from app.services.research.fetch_cache import FetchCache
from app.services.research.fetcher import ControlledFetcher, validate_public_url
from app.services.research.schemas import (
    EnrichedWebEvidence,
    ProductResearchResult,
    ResearchEvidence,
    ResearchResponse,
)
from app.services.spreadsheets.schemas import Product


PUBLIC_IP = ["93.184.216.34"]
HTML = b"""<!doctype html><html><head>
<title>Raspberry Pi 5 product page</title>
<meta name="description" content="Raspberry Pi 5 single-board computer">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Raspberry Pi 5",
 "sku":"RPI5-8GB","mpn":"SC1112","model":"Raspberry Pi 5",
 "brand":{"@type":"Brand","name":"Raspberry Pi"},
 "manufacturer":{"@type":"Organization","name":"Raspberry Pi"},
 "material":"100% cotton","color":"green","category":"single-board computer",
 "description":"A fast single-board computer","url":"https://example.com/product"}
</script></head><body>
<nav>Navigation noise</nav><div class="cookie-banner">Accept cookies</div>
<main><h1>Raspberry Pi 5</h1><h2>Technical specifications</h2>
<p>Raspberry Pi 5 is a single-board computer manufactured by Raspberry Pi.</p>
<table><tr><th>Model</th><td>Raspberry Pi 5</td></tr></table></main>
<footer>Footer noise</footer><script>ignoreMe()</script></body></html>"""


def public_resolver(_host: str, _port: int) -> list[str]:
    return PUBLIC_IP


def make_product(code: str = "Raspberry Pi 5") -> Product:
    return Product(
        product_id=code,
        code=code,
        code_original=code,
        code_confidence=1.0,
        sheet_name="Packing",
        row_numbers=[2],
        item_name="single-board computer",
        manufacturer="Raspberry Pi",
        brand="Raspberry Pi",
        composition="100% polyester",
    )


def make_fetcher(tmp_path: Path, handler, *, max_bytes: int = 3_145_728) -> ControlledFetcher:
    return ControlledFetcher(
        cache=FetchCache(tmp_path / "fetch-cache", 3600),
        timeout_seconds=2,
        max_bytes=max_bytes,
        transport=httpx.MockTransport(handler),
        resolver=public_resolver,
    )


def test_fetch_extracts_html_meta_headings_json_ld_and_product_signals(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=HTML)

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/product"))
    matched = apply_product_matching(fetched, make_product())

    assert fetched.fetch_status == "OK"
    assert fetched.title == "Raspberry Pi 5 product page"
    assert fetched.meta_description == "Raspberry Pi 5 single-board computer"
    assert fetched.headings == ["Raspberry Pi 5", "Technical specifications"]
    assert "Navigation noise" not in fetched.text_excerpt
    assert "Accept cookies" not in fetched.text_excerpt
    product = fetched.structured_data["items"][0]
    assert product["sku"] == "RPI5-8GB"
    assert product["manufacturer"] == "Raspberry Pi"
    assert product["material"] == "100% cotton"
    assert {"code", "item_name", "manufacturer", "brand"} <= set(matched.matched_signals)
    assert matched.content_hash and len(matched.content_hash) == 64
    assert matched.bytes_downloaded == len(HTML)


def test_conflict_preserves_spreadsheet_and_web_sources(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/product"))
    matched = apply_product_matching(fetched, make_product())

    conflict = next(item for item in matched.conflicts if item.field == "composition")
    assert conflict.spreadsheet.value == "100% polyester"
    assert conflict.spreadsheet.source_type == "spreadsheet"
    assert conflict.web.value == "100% cotton"
    assert conflict.web.source_url == "https://example.com/product"
    assert any(
        fact.field == "composition"
        and fact.value == "100% polyester"
        and fact.source_type == "spreadsheet"
        for fact in matched.source_facts
    )


def test_safe_redirect_is_revalidated_and_followed(tmp_path: Path) -> None:
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://example.com/product"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/start"))

    assert fetched.fetch_status == "OK"
    assert fetched.final_url == "https://example.com/product"
    assert seen == ["https://example.com/start", "https://example.com/product"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/", "http://127.0.0.1/", "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/", "http://[::1]/",
        "file:///etc/passwd", "ftp://example.com/file", "gopher://example.com/",
        "data:text/plain,test", "javascript:alert(1)", "https://example.com:8443/",
    ],
)
def test_ssrf_blocks_local_private_metadata_schemes_and_nonstandard_ports(url: str) -> None:
    with pytest.raises(ValueError):
        asyncio.run(validate_public_url(url, public_resolver))


def test_ssrf_blocks_private_ip_returned_by_dns() -> None:
    with pytest.raises(ValueError):
        asyncio.run(validate_public_url("https://example.com/", lambda _host, _port: ["192.168.1.10"]))


def test_redirect_to_private_address_is_blocked(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/start"))
    assert fetched.fetch_status == "SSRF_BLOCKED"


def test_rejects_large_response_from_header_and_stream(tmp_path: Path) -> None:
    async def header_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html", "content-length": "101"}, content=b"x")

    async def body_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 101)

    assert asyncio.run(make_fetcher(tmp_path, header_handler, max_bytes=100).fetch("https://example.com/a")).fetch_status == "TOO_LARGE"
    assert asyncio.run(make_fetcher(tmp_path, body_handler, max_bytes=100).fetch("https://example.com/b")).fetch_status == "TOO_LARGE"


def test_rejects_unsupported_content_type(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/manual.pdf"))
    assert fetched.fetch_status == "UNSUPPORTED_CONTENT"


def test_timeout_has_explicit_status(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    fetched = asyncio.run(make_fetcher(tmp_path, handler).fetch("https://example.com/slow"))
    assert fetched.fetch_status == "TIMEOUT"


def test_blocked_response_is_cached_to_avoid_repeated_requests(tmp_path: Path) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403)

    fetcher = make_fetcher(tmp_path, handler)
    first = asyncio.run(fetcher.fetch("https://example.com/protected"))
    second = asyncio.run(fetcher.fetch("https://example.com/protected"))

    assert first.fetch_status == "BLOCKED"
    assert second.fetch_status == "BLOCKED"
    assert second.cache_status == "HIT"
    assert calls == 1


def test_expired_fetch_cache_is_reported_and_refetched(tmp_path: Path, monkeypatch) -> None:
    calls = 0
    clock = {"value": 100.0}
    monkeypatch.setattr(fetch_cache_module.time, "time", lambda: clock["value"])

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    fetcher = ControlledFetcher(
        cache=FetchCache(tmp_path / "fetch-cache", 10), timeout_seconds=2,
        max_bytes=3_145_728, transport=httpx.MockTransport(handler), resolver=public_resolver,
    )
    first = asyncio.run(fetcher.fetch("https://example.com/product"))
    clock["value"] = 111.0
    second = asyncio.run(fetcher.fetch("https://example.com/product"))

    assert first.cache_status == "MISS"
    assert second.cache_status == "EXPIRED"
    assert calls == 2


@pytest.mark.parametrize(
    ("encoding", "compress"),
    [("gzip", gzip.compress), ("br", brotli.compress)],
)
def test_compression_is_decoded_and_fetch_cache_avoids_second_request(
    tmp_path: Path, encoding: str, compress,
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-encoding": encoding},
            content=compress(HTML),
        )

    fetcher = make_fetcher(tmp_path, handler)
    first = asyncio.run(fetcher.fetch("https://example.com/product"))
    second = asyncio.run(fetcher.fetch("https://example.com/product"))

    assert first.fetch_status == "OK"
    assert first.cache_status == "MISS"
    assert second.cache_status == "HIT"
    assert second.title == first.title
    assert calls == 1


def research_evidence(url: str, strength: str) -> ResearchEvidence:
    return ResearchEvidence(
        title="Product", url=url, snippet="Product evidence", provider="searxng-search",
        source_engine="bing", domain="example.com", source_category="UNKNOWN",
        evidence_strength=strength, position=1, retrieved_at=datetime.now(UTC),
        query='"MODEL"', score=10, relevance_reasons=["test"],
    )


def test_enrichment_fetches_only_approved_and_skips_not_found(tmp_path: Path) -> None:
    calls: list[str] = []

    class FakeFetcher:
        async def fetch(self, url: str, *, refresh_cache: bool = False) -> EnrichedWebEvidence:
            calls.append(url)
            return EnrichedWebEvidence(
                url=url, final_url=url, domain="example.com", http_status=200,
                content_type="text/html", fetch_status="OK", fetched_at=datetime.now(UTC),
                title="MODEL product", text_excerpt="MODEL product", cache_status="MISS",
            )

    found = make_product("MODEL")
    not_found = make_product("PRIVATE-STYLE")
    research = ResearchResponse(
        file_id="file", provider="searxng-search", researched_at=datetime.now(UTC),
        products=[
            ProductResearchResult(
                product_id="MODEL", code="MODEL", status="OK", queries=[],
                evidences=[
                    research_evidence("https://example.com/strong", "STRONG"),
                    research_evidence("https://example.com/weak", "WEAK"),
                    research_evidence("https://example.com/moderate", "MODERATE"),
                    research_evidence("https://example.com/third", "STRONG"),
                    research_evidence("https://example.com/fourth", "STRONG"),
                ],
            ),
            ProductResearchResult(
                product_id="PRIVATE-STYLE", code="PRIVATE-STYLE", status="NÃO_ENCONTRADO",
                queries=[], evidences=[],
            ),
        ],
        query_count=2, gateway_calls=0, cache_hits=2, cache_misses=0, llm_used=False,
    )
    service = EvidenceEnrichmentService(
        Settings(upload_dir=tmp_path, fetch_cache_dir=tmp_path / "fetch-cache"),
        fetcher=FakeFetcher(),  # type: ignore[arg-type]
    )
    response = asyncio.run(service.enrich(
        "file", [found, not_found], research,
        max_pages_per_product=3, refresh_fetch_cache=False,
    ))

    assert calls == [
        "https://example.com/strong",
        "https://example.com/moderate",
        "https://example.com/third",
    ]
    assert response.products[0].approved_urls == 3
    assert response.products[1].approved_urls == 0
    assert response.products[1].fetches == []
    assert response.fetch_requests == 3
    assert response.llm_used is False
