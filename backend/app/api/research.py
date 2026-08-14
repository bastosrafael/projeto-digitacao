from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.services.research.enrichment import EvidenceEnrichmentService
from app.services.research.analysis import EvidenceAnalysisService
from app.services.research.analysis_schemas import AnalysisRequest, AnalysisResponse
from app.services.research.multimodal import MultimodalAnalysisService
from app.services.research.multimodal_schemas import MultimodalRequest, MultimodalResponse
from app.services.research import ProductResearchService
from app.services.research.schemas import (
    EnrichmentRequest,
    EnrichmentResponse,
    ResearchRequest,
    ResearchResponse,
)
from app.services.spreadsheets import analyze_workbook
from app.services.spreadsheets.parser import SpreadsheetParseError
from app.services.spreadsheets.images import ProductImageError, extract_product_image_bytes

router = APIRouter(prefix="/api/uploads", tags=["research"])


async def _load_products(file_id: UUID, product_ids: list[str], settings: Settings):
    controlled_file_id = str(file_id)
    path = settings.upload_dir / f"{controlled_file_id}.xlsx"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload não encontrado.")
    try:
        analysis = await run_in_threadpool(analyze_workbook, path, controlled_file_id)
    except SpreadsheetParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    requested = list(dict.fromkeys(product_ids))
    if len(requested) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="product_ids deve conter somente produtos distintos.",
        )
    by_id = {product.product_id: product for product in analysis.products}
    missing = [product_id for product_id in requested if product_id not in by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Produto(s) não encontrado(s) no upload: {', '.join(missing)}.",
        )
    products = [by_id[product_id] for product_id in requested]
    without_queries = [product.product_id for product in products if not product.research_preparation.queries]
    if without_queries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Produto(s) sem evidência suficiente para pesquisa: {', '.join(without_queries)}.",
        )
    return controlled_file_id, products


@router.post("/{file_id}/research", response_model=ResearchResponse)
async def research_products(
    file_id: UUID,
    request: ResearchRequest,
    settings: Settings = Depends(get_settings),
) -> ResearchResponse:
    controlled_file_id, products = await _load_products(file_id, request.product_ids, settings)

    return await ProductResearchService(settings).research(
        controlled_file_id,
        products,
        max_queries_per_product=request.max_queries_per_product,
        max_results_per_query=request.max_results_per_query,
        refresh_cache=request.refresh_cache,
    )


@router.post("/{file_id}/research/enrich", response_model=EnrichmentResponse)
async def enrich_research_evidence(
    file_id: UUID,
    request: EnrichmentRequest,
    settings: Settings = Depends(get_settings),
) -> EnrichmentResponse:
    controlled_file_id, products = await _load_products(file_id, request.product_ids, settings)
    research = await ProductResearchService(settings).research(
        controlled_file_id,
        products,
        max_queries_per_product=request.max_queries_per_product,
        max_results_per_query=request.max_results_per_query,
        refresh_cache=request.refresh_cache,
    )
    return await EvidenceEnrichmentService(settings).enrich(
        controlled_file_id,
        products,
        research,
        max_pages_per_product=request.max_pages_per_product,
        refresh_fetch_cache=request.refresh_fetch_cache,
    )


@router.post("/{file_id}/research/analyze", response_model=AnalysisResponse)
async def analyze_research_evidence(
    file_id: UUID,
    request: AnalysisRequest,
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    controlled_file_id, products = await _load_products(file_id, request.product_ids, settings)
    research = await ProductResearchService(settings).research(
        controlled_file_id,
        products,
        max_queries_per_product=request.max_queries_per_product,
        max_results_per_query=request.max_results_per_query,
        refresh_cache=request.refresh_cache,
    )
    enrichment = await EvidenceEnrichmentService(settings).enrich(
        controlled_file_id,
        products,
        research,
        max_pages_per_product=request.max_pages_per_product,
        refresh_fetch_cache=request.refresh_fetch_cache,
    )
    return await EvidenceAnalysisService(settings).analyze(
        controlled_file_id,
        products,
        enrichment,
        refresh_cache=request.refresh_analysis_cache,
    )


@router.post("/{file_id}/research/multimodal", response_model=MultimodalResponse)
async def analyze_multimodal_evidence(
    file_id: UUID,
    request: MultimodalRequest,
    settings: Settings = Depends(get_settings),
) -> MultimodalResponse:
    controlled_file_id, products = await _load_products(file_id, request.product_ids, settings)
    path = settings.upload_dir / f"{controlled_file_id}.xlsx"
    images = {}
    for product in products:
        images[product.product_id] = None
        if product.code and product.images.product:
            try:
                images[product.product_id] = await run_in_threadpool(
                    extract_product_image_bytes, path, product.code, product.images.product[0]
                )
            except ProductImageError:
                # A ausência/falha visual não derruba a análise textual controlada.
                images[product.product_id] = "PRODUCT_IMAGE_INVALID"
    research = await ProductResearchService(settings).research(
        controlled_file_id,
        products,
        max_queries_per_product=request.max_queries_per_product,
        max_results_per_query=request.max_results_per_query,
        refresh_cache=request.refresh_cache,
    )
    enrichment = await EvidenceEnrichmentService(settings).enrich(
        controlled_file_id,
        products,
        research,
        max_pages_per_product=request.max_pages_per_product,
        refresh_fetch_cache=request.refresh_fetch_cache,
    )
    return await MultimodalAnalysisService(settings).analyze(
        controlled_file_id,
        products,
        images,
        enrichment,
        refresh_visual_cache=request.refresh_visual_cache,
        refresh_multimodal_cache=request.refresh_multimodal_cache,
    )
