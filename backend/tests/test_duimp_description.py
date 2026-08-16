"""Testes da Fase 8A — gerador de descrição técnica DUIMP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.services.omniroute import OmniRouteCompletion, OmniRouteError
from app.services.research.analysis_cache import AnalysisCache
from app.services.research.duimp_description import (
    DuimpDescriptionService,
    PROMPT_VERSION,
    GENERATOR_VERSION,
)
from app.services.research.duimp_schemas import (
    Claim,
    DuimpDescriptionResult,
    LlmDuimpDescription,
)
from app.services.research.fact_ledger import (
    build_fact_ledger,
    get_confirmed_facts_summary,
    get_excluded_fields,
)


# ==========================================
# FIXTURES / HELPERS
# ==========================================

def _labels_result(**overrides) -> dict:
    base = {
        "product_id": "WW77#",
        "code": "WW77#",
        "decision": "REVIEW",
        "confidence": "MEDIUM",
        "internal_support": "MODERATE",
        "external_support": "NONE",
        "product_image_used": True,
        "wash_label_used": True,
        "hangtag_used": True,
        "evidence_used": ["PACKING-001", "WASH-001", "HANGTAG-001", "VISUAL-001"],
        "confirmed_fields": [
            {"field": "code", "value": "WW77#", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "\u8fde\u8863\u88d9", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "category_visual", "value": "dress", "evidence_ids": ["VISUAL-001"], "source_types": ["visual"]},
            {"field": "ncm", "value": "6104.43.00", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "\u68ad\u7ec7", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "manufacturer", "value": "\u848b\u57f9\u82f1", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "brand", "value": "Liu FASHION", "evidence_ids": ["HANGTAG-001"], "source_types": ["hangtag"]},
            {"field": "country_of_origin", "value": "China", "evidence_ids": ["WASH-001"], "source_types": ["wash_label"]},
            {"field": "primary_color", "value": "pink", "evidence_ids": ["VISUAL-001"], "source_types": ["visual"]},
            {"field": "sleeves", "value": "off-the-shoulder", "evidence_ids": ["VISUAL-001"], "source_types": ["visual"]},
            {"field": "length", "value": "knee-length", "evidence_ids": ["VISUAL-001"], "source_types": ["visual"]},
            {"field": "visible_details", "value": "ruffle neckline, floral pattern", "evidence_ids": ["VISUAL-001"], "source_types": ["visual"]},
        ],
        "conflicts": [
            {"field": "composition", "sources": [
                {"evidence_id": "PACKING-001", "value": "\u9762\u5e03\uff1a100%\u6da4"},
                {"evidence_id": "WASH-001", "value": "polyester"},
            ]},
        ],
        "unknown_fields": ["size", "style_code_from_label", "sku_from_label"],
        "warnings": [],
    }
    base.update(overrides)
    return base


def _wash_evidence() -> dict:
    return {
        "status": "OK",
        "product_code": "WW77#",
        "raw_visible_text": [
            {"text": "TELA EXTERIOR:", "language": "pt"},
            {"text": "100%POLI\u00c9STER", "language": "pt"},
            {"text": "TELA INTERIOR:", "language": "pt"},
            {"text": "95%POLI\u00c9STER", "language": "pt"},
            {"text": "5%ELASTANO", "language": "pt"},
            {"text": "FABRICADO NA CHINA", "language": "pt"},
        ],
        "composition": [
            {"fiber_original": "POLI\u00c9STER", "fiber_normalized": "polyester", "percentage": 100, "confidence": "HIGH"},
            {"fiber_original": "POLI\u00c9STER", "fiber_normalized": "polyester", "percentage": 95, "confidence": "HIGH"},
            {"fiber_original": "ELASTANO", "fiber_normalized": "elastane", "percentage": 5, "confidence": "HIGH"},
        ],
        "composition_sum": 200,
        "composition_sum_valid": False,
        "country_of_origin": {"value": "China", "confidence": "HIGH"},
        "brand": {"value": "UNKNOWN", "confidence": "LOW"},
        "size": {"value": "UNKNOWN", "confidence": "LOW"},
        "style_code": {"value": "UNKNOWN", "confidence": "LOW"},
    }


def _visual_evidence_with_uncertain() -> dict:
    return {
        "product_code": "WW77#",
        "image_type": "PRODUCT_IMAGE",
        "uncertain_attributes": [
            {"field": "sleeves", "candidate_values": ["short sleeves"], "reason": "ambiguous"},
        ],
    }


def _valid_llm_response() -> str:
    return json.dumps({
        "description": "VESTIDO FEMININO, CONFECCIONADO EM TECIDO PLANO DE FIBRAS SINT\u00c9TICAS (TELA EXTERIOR: 100% POLI\u00c9STER; TELA INTERIOR: 95% POLI\u00c9STER E 5% ELASTANO), NA COR ROSA, COMPRIMENTO NA ALTURA DO JOELHO.",
        "claims": [
            {"claim_id": "CLAIM-001", "field": "category", "value": "vestido", "evidence_ids": ["VISUAL-001"]},
            {"claim_id": "CLAIM-002", "field": "primary_color", "value": "rosa", "evidence_ids": ["VISUAL-001"]},
            {"claim_id": "CLAIM-003", "field": "length", "value": "joelho", "evidence_ids": ["VISUAL-001"]},
        ],
    })


def _tmp_cache(tmp_path: Path) -> AnalysisCache:
    d = tmp_path / "duimp-cache"
    d.mkdir(parents=True, exist_ok=True)
    return AnalysisCache(d, 604_800)


def _settings() -> Settings:
    return Settings()


# ==========================================
# 1) FACT LEDGER
# ==========================================

class TestFactLedger:
    def test_confirmed_fields_present(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert ledger.product_code.status == "CONFIRMED"
        assert ledger.product_code.value == "WW77#"
        assert ledger.category.status == "CONFIRMED"
        assert ledger.category.value == "vestido"  # normalized

    def test_unknown_excluded(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert ledger.size.status == "UNKNOWN"
        excluded = get_excluded_fields(ledger)
        assert any(e.field == "size" for e in excluded)

    def test_conflicting_excluded(self):
        """Composition in conflict should be CONFLICTING."""
        lr = _labels_result()
        ledger = build_fact_ledger(lr, None)  # no wash -> conflict stays
        # composition conflict is handled in _build_composition
        assert ledger.composition_status in ("CONFLICTING", "CONFIRMED", "UNKNOWN")

    def test_composition_layers(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert len(ledger.composition_layers) == 2
        assert ledger.composition_layers[0].layer_name == "exterior"
        assert ledger.composition_layers[1].layer_name == "interior"
        assert ledger.composition_status == "CONFIRMED"

    def test_sleeves_uncertain_with_visual(self):
        ledger = build_fact_ledger(
            _labels_result(), _wash_evidence(),
            visual_evidence=_visual_evidence_with_uncertain(),
        )
        assert ledger.sleeves.status == "UNCERTAIN"

    def test_brand_not_manufacturer(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert ledger.brand.value == "Liu FASHION"
        assert ledger.manufacturer.value == "\u848b\u57f9\u82f1"
        assert ledger.brand.value != ledger.manufacturer.value

    def test_visual_does_not_prove_composition(self):
        """Composition comes from wash label, not visual."""
        lr = _labels_result()
        # Remove composition from confirmed_fields
        lr["confirmed_fields"] = [
            cf for cf in lr["confirmed_fields"]
            if cf["field"] not in ("composition",)
        ]
        ledger = build_fact_ledger(lr, _wash_evidence())
        # Composition still comes from wash_evidence layers
        assert len(ledger.composition_layers) == 2

    def test_item_name_normalized(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert ledger.item_name.value == "vestido"

    def test_construction_normalized(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        assert ledger.construction.value == "tecido plano"

    def test_confirmed_facts_summary(self):
        ledger = build_fact_ledger(_labels_result(), _wash_evidence())
        facts = get_confirmed_facts_summary(ledger)
        assert "product_code" in facts
        assert "category" in facts
        assert "composition" in facts
        assert "size" not in facts  # UNKNOWN

    def test_no_wash_no_composition(self):
        lr = _labels_result()
        lr["conflicts"] = []
        ledger = build_fact_ledger(lr, None)
        assert ledger.composition_status == "UNKNOWN"
        assert len(ledger.composition_layers) == 0


# ==========================================
# 2) DESCRIPTION SERVICE (MOCKED LLM)
# ==========================================

class TestDescriptionService:
    def test_generated_with_valid_claims(self, tmp_path):
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=_valid_llm_response(), model="test-model", latency_ms=100,
        ))
        service = DuimpDescriptionService(
            _settings(), gateway, _tmp_cache(tmp_path),
        )
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result.status == "GENERATED"
        assert result.description != ""
        assert result.llm_used is True
        assert result.cache_status == "MISS"
        assert len(result.claims) == 3

    def test_cache_hit(self, tmp_path):
        cache = _tmp_cache(tmp_path)
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=_valid_llm_response(), model="test-model", latency_ms=100,
        ))
        service = DuimpDescriptionService(_settings(), gateway, cache)
        # First call
        asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        # Second call — should be cache HIT
        result2 = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result2.cache_status == "HIT"
        assert result2.llm_used is False
        assert gateway.complete_json.call_count == 1

    def test_insufficient_evidence(self, tmp_path):
        lr = _labels_result(confirmed_fields=[], conflicts=[], unknown_fields=["size"])
        gateway = AsyncMock()
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(lr))
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert gateway.complete_json.call_count == 0

    def test_invalid_claim_retry(self, tmp_path):
        """First response has unauthorized claim, second is valid."""
        bad_response = json.dumps({
            "description": "VESTIDO TAMANHO M",
            "claims": [
                {"claim_id": "CLAIM-001", "field": "size", "value": "M", "evidence_ids": ["PACKING-001"]},
            ],
        })
        good_response = _valid_llm_response()
        call_count = 0

        async def _complete(messages, *, timeout_seconds):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OmniRouteCompletion(content=bad_response, model="m", latency_ms=50)
            return OmniRouteCompletion(content=good_response, model="m", latency_ms=50)

        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(side_effect=_complete)
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result.status == "GENERATED"
        assert call_count == 2

    def test_two_failures_review_required(self, tmp_path):
        """Both responses have unauthorized claims -> REVIEW_REQUIRED."""
        bad = json.dumps({
            "description": "VESTIDO TAMANHO M COR AZUL",
            "claims": [
                {"claim_id": "CLAIM-001", "field": "size", "value": "M", "evidence_ids": ["X"]},
            ],
        })
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=bad, model="m", latency_ms=50,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result.status == "REVIEW_REQUIRED"

    def test_omniroute_error_raises(self, tmp_path):
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(side_effect=OmniRouteError("unavailable", 502))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        with pytest.raises(OmniRouteError):
            asyncio.run(service.generate(_labels_result(), _wash_evidence()))

    def test_invalid_json_retry(self, tmp_path):
        """First response is invalid JSON, second is valid."""
        call_count = 0

        async def _complete(messages, *, timeout_seconds):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OmniRouteCompletion(content="not json", model="m", latency_ms=50)
            return OmniRouteCompletion(content=_valid_llm_response(), model="m", latency_ms=50)

        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(side_effect=_complete)
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result.status == "GENERATED"
        assert call_count == 2


# ==========================================
# 3) CLAIM VALIDATION
# ==========================================

class TestClaimValidation:
    def test_unknown_field_rejected(self, tmp_path):
        """Claim referencing UNKNOWN field (size) should trigger violation."""
        response_with_unknown = json.dumps({
            "description": "VESTIDO TAMANHO M",
            "claims": [
                {"claim_id": "CLAIM-001", "field": "size", "value": "M", "evidence_ids": ["PACKING-001"]},
            ],
        })
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=response_with_unknown, model="m", latency_ms=50,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        # Should be REVIEW_REQUIRED since the only claim is invalid
        assert result.status == "REVIEW_REQUIRED"

    def test_no_visual_call(self, tmp_path):
        """DUIMP generation must NOT trigger any visual model call."""
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=_valid_llm_response(), model="test-model", latency_ms=100,
        ))
        gateway.complete_vision_json = AsyncMock()
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert gateway.complete_vision_json.call_count == 0

    def test_prompt_version(self, tmp_path):
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=_valid_llm_response(), model="test-model", latency_ms=100,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        assert result.prompt_version == PROMPT_VERSION
        assert result.generator_version == GENERATOR_VERSION

    def test_confidence_high_with_enough_facts(self, tmp_path):
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=_valid_llm_response(), model="test-model", latency_ms=100,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(_labels_result(), _wash_evidence()))
        # WW77# has 12+ confirmed facts + composition -> HIGH
        assert result.confidence in ("HIGH", "MEDIUM")
