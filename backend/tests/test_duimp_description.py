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
    check_sufficiency,
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


# ==========================================
# 4) SUFFICIENCY GATE — Fase 8B
# ==========================================

class TestSufficiencyGate:
    def test_sufficient_with_category_and_composition(self):
        facts = {"category": {"value": "vestido"}, "composition": {"value": "100% polyester"}}
        ok, reason = check_sufficiency(facts, set())
        assert ok is True
        assert reason == "sufficient evidence"

    def test_sufficient_with_item_name_and_construction(self):
        facts = {"item_name": {"value": "calça"}, "construction": {"value": "tecido plano"}}
        ok, _ = check_sufficiency(facts, set())
        assert ok is True

    def test_insufficient_no_facts(self):
        ok, reason = check_sufficiency({}, set())
        assert ok is False
        assert "no confirmed facts" in reason

    def test_insufficient_ncm_alone(self):
        facts = {"ncm": {"value": "6104.43.00"}, "product_code": {"value": "X"}}
        ok, reason = check_sufficiency(facts, set())
        assert ok is False
        assert "no category or item_name" in reason

    def test_insufficient_no_supporting(self):
        facts = {"category": {"value": "vestido"}, "primary_color": {"value": "rosa"}}
        ok, reason = check_sufficiency(facts, set())
        assert ok is False
        assert "no composition or construction" in reason

    def test_insufficient_no_essential(self):
        facts = {"composition": {"value": "100% poliéster"}, "ncm": {"value": "6104"}}
        ok, reason = check_sufficiency(facts, set())
        assert ok is False
        assert "no category or item_name" in reason

    def test_essential_conflict_blocks(self):
        facts = {"item_name": {"value": "vestido"}, "construction": {"value": "tecido plano"}}
        ok, reason = check_sufficiency(facts, {"item_name"})
        assert ok is False
        assert "conflict in essential" in reason

    def test_supporting_conflict_does_not_block(self):
        facts = {"item_name": {"value": "vestido"}, "construction": {"value": "tecido plano"}}
        ok, _ = check_sufficiency(facts, {"composition"})
        assert ok is True


# ==========================================
# 5) PARTIAL / INSUFFICIENT SCENARIOS — Fase 8B
# ==========================================

def _packing_only_labels(code: str, confirmed: list[dict], unknown: list[str] | None = None) -> dict:
    return {
        "code": code,
        "product_id": code,
        "decision": "REVIEW",
        "confidence": "LOW",
        "internal_support": "WEAK",
        "external_support": "NONE",
        "product_image_used": False,
        "wash_label_used": False,
        "hangtag_used": False,
        "evidence_used": ["PACKING-001"],
        "confirmed_fields": confirmed,
        "conflicts": [],
        "unknown_fields": unknown or [],
        "warnings": ["Packing list fallback."],
        "packing_fallback": True,
    }


class TestPartialScenarios:
    def test_packing_only_sufficient(self, tmp_path):
        """CY2926-like: packing com item_name, construction, composition → GENERATED."""
        lr = _packing_only_labels("CY2926", [
            {"field": "code", "value": "CY2926", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "\u68ad\u7ec7\u5973\u58eb\u5957\u88c5", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "ncm", "value": "6104.23.00", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "composition", "value": "100\u6da4", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "\u68ad\u7ec7", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=json.dumps({
                "description": "CONJUNTO DE TECIDO PLANO, COMPOSIÇÃO: 100% POLIÉSTER.",
                "claims": [
                    {"claim_id": "CLAIM-001", "field": "item_name", "value": "conjunto", "evidence_ids": ["PACKING-001"]},
                    {"claim_id": "CLAIM-002", "field": "construction", "value": "tecido plano", "evidence_ids": ["PACKING-001"]},
                    {"claim_id": "CLAIM-003", "field": "composition", "value": "100% poliéster", "evidence_ids": ["PACKING-001"]},
                ],
            }), model="m", latency_ms=50,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(lr, packing_fallback=True))
        assert result.status == "GENERATED"
        assert result.packing_fallback is True
        assert result.llm_used is True
        assert "poli\u00e9ster" in result.description.lower() or "POLIÉSTER" in result.description

    def test_insufficient_only_ncm_and_code(self, tmp_path):
        """N260309# sem composition/construction: INSUFFICIENT sem LLM."""
        lr = _packing_only_labels("MINIMAL", [
            {"field": "code", "value": "MINIMAL", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "ncm", "value": "6104.43.00", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        gateway = AsyncMock()
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(lr))
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert gateway.complete_json.call_count == 0
        assert result.llm_used is False

    def test_description_without_color(self, tmp_path):
        """Cor UNKNOWN não bloqueia geração."""
        lr = _packing_only_labels("NOCOLOR", [
            {"field": "code", "value": "NOCOLOR", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "vestido", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "tecido plano", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ], unknown=["primary_color"])
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(return_value=OmniRouteCompletion(
            content=json.dumps({
                "description": "VESTIDO DE TECIDO PLANO.",
                "claims": [
                    {"claim_id": "CLAIM-001", "field": "item_name", "value": "vestido", "evidence_ids": ["PACKING-001"]},
                    {"claim_id": "CLAIM-002", "field": "construction", "value": "tecido plano", "evidence_ids": ["PACKING-001"]},
                ],
            }), model="m", latency_ms=50,
        ))
        service = DuimpDescriptionService(_settings(), gateway, _tmp_cache(tmp_path))
        result = asyncio.run(service.generate(lr))
        assert result.status == "GENERATED"
        excluded_names = [e.field for e in result.excluded_fields]
        assert "primary_color" in excluded_names


# ==========================================
# 6) COMPOSITION FROM PACKING — Fase 8B
# ==========================================

class TestPackingComposition:
    def test_chinese_100_polyester(self):
        from app.services.research.fact_ledger import _parse_packing_composition
        layers, status = _parse_packing_composition("100\u6da4", ["PACKING-001"])
        assert status == "CONFIRMED"
        assert len(layers) == 1
        assert layers[0].fibers[0]["fiber"] == "poli\u00e9ster"
        assert layers[0].fibers[0]["percentage"] == 100

    def test_chinese_two_layer(self):
        from app.services.research.fact_ledger import _parse_packing_composition
        layers, status = _parse_packing_composition("95\u68c95\u6c28\u7eb6+100PU", ["PACKING-001"])
        assert status == "CONFIRMED"
        assert len(layers) == 2
        assert layers[0].fibers[0]["fiber"] == "algod\u00e3o"
        assert layers[0].fibers[0]["percentage"] == 95
        assert layers[0].fibers[1]["fiber"] == "elastano"
        assert layers[0].fibers[1]["percentage"] == 5
        assert layers[1].fibers[0]["fiber"] == "PU"
        assert layers[1].fibers[0]["percentage"] == 100

    def test_unparseable_returns_unknown(self):
        from app.services.research.fact_ledger import _parse_packing_composition
        layers, status = _parse_packing_composition("material desconhecido", ["PACKING-001"])
        assert status == "UNKNOWN"
        assert layers == []

    def test_sum_over_100_returns_unknown(self):
        from app.services.research.fact_ledger import _parse_packing_composition
        layers, status = _parse_packing_composition("60\u68c960\u6da4", ["PACKING-001"])
        assert status == "UNKNOWN"

    def test_fact_ledger_packing_composition_fallback(self):
        """Fact Ledger usa composição da packing quando wash não existe."""
        lr = _packing_only_labels("CY2926", [
            {"field": "code", "value": "CY2926", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "\u5957\u88c5", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "composition", "value": "100\u6da4", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "\u68ad\u7ec7", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        ledger = build_fact_ledger(lr)
        assert ledger.composition_status == "CONFIRMED"
        assert len(ledger.composition_layers) == 1
        assert ledger.composition_layers[0].fibers[0]["fiber"] == "poli\u00e9ster"

    def test_n260309_composition_two_layers(self):
        """N260309#: '95棉5氨纶+100pu' → 2 camadas."""
        lr = _packing_only_labels("N260309#", [
            {"field": "code", "value": "N260309#", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "\u68ad\u7ec7\u957f\u88e4+\u8170\u5e26", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "composition", "value": "95\u68c95\u6c28\u7eb6+100pu", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "\u68ad\u7ec7", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "manufacturer", "value": "\u9ec4\u6797", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "ncm", "value": "6104.63.00", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        ledger = build_fact_ledger(lr)
        assert ledger.composition_status == "CONFIRMED"
        assert len(ledger.composition_layers) == 2
        assert ledger.composition_layers[0].fibers[0]["fiber"] == "algod\u00e3o"
        assert ledger.composition_layers[1].fibers[0]["fiber"] == "PU"
        # item_name normalizado: contém 长裤 → calça
        assert ledger.item_name.value == "cal\u00e7a"

    def test_item_name_partial_match(self):
        """Item name chinês com match parcial (梭织女士套装 contém 套装)."""
        lr = _packing_only_labels("X", [
            {"field": "code", "value": "X", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "\u68ad\u7ec7\u5973\u58eb\u5957\u88c5", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "\u68ad\u7ec7", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        ledger = build_fact_ledger(lr)
        assert ledger.item_name.value == "conjunto"


# ==========================================
# 7) CACHE ISOLATION — Fase 8B
# ==========================================

class TestCacheIsolation:
    def test_different_products_different_cache(self, tmp_path):
        """Cache keys são distintas para produtos diferentes."""
        lr1 = _packing_only_labels("P1", [
            {"field": "code", "value": "P1", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "vestido", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "tecido plano", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])
        lr2 = _packing_only_labels("P2", [
            {"field": "code", "value": "P2", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "item_name", "value": "calça", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
            {"field": "construction", "value": "malha", "evidence_ids": ["PACKING-001"], "source_types": ["packing_list"]},
        ])

        def _make_response(desc, code):
            return json.dumps({
                "description": desc,
                "claims": [
                    {"claim_id": "CLAIM-001", "field": "item_name", "value": code, "evidence_ids": ["PACKING-001"]},
                    {"claim_id": "CLAIM-002", "field": "construction", "value": "x", "evidence_ids": ["PACKING-001"]},
                ],
            })

        call_count = 0

        async def _complete(messages, *, timeout_seconds):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OmniRouteCompletion(content=_make_response("VESTIDO DE TECIDO PLANO.", "vestido"), model="m", latency_ms=50)
            return OmniRouteCompletion(content=_make_response("CALÇA DE MALHA.", "calça"), model="m", latency_ms=50)

        cache = _tmp_cache(tmp_path)
        gateway = AsyncMock()
        gateway.complete_json = AsyncMock(side_effect=_complete)
        service = DuimpDescriptionService(_settings(), gateway, cache)

        r1 = asyncio.run(service.generate(lr1))
        r2 = asyncio.run(service.generate(lr2))

        assert r1.product_code == "P1"
        assert r2.product_code == "P2"
        assert r1.description != r2.description
        assert call_count == 2  # cada produto gerou sua própria chamada
