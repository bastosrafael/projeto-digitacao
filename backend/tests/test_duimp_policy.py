from app.services.duimp_policy import (
    build_description_preparation,
    build_research_preparation,
)
from app.services.spreadsheets.schemas import Product


def product(**values: object) -> Product:
    return Product(
        product_id="TEST-1",
        code_confidence=0.99,
        sheet_name="Produtos",
        row_numbers=[2],
        **values,
    )


def test_research_uses_only_provided_evidence_and_treats_ncm_as_unconfirmed() -> None:
    item = product(
        code="TX26",
        item_name="Fone de ouvido sem fio",
        ncm="8518.30.00",
        brand="Exemplo",
        connection="Bluetooth 5.0",
    )

    preparation = build_research_preparation(item)

    assert preparation.queries == [
        '"TX26"',
        '"TX26" "Fone de ouvido sem fio"',
        '"TX26" "Exemplo"',
        '"TX26" "Bluetooth 5.0"',
    ]
    assert preparation.evidence_terms["ncm"] == "8518.30.00"
    assert preparation.evidence_terms["connection"] == "Bluetooth 5.0"
    assert "A NCM da planilha é termo de pesquisa" in preparation.warnings[0]
    assert "modo de funcionamento" in preparation.focus_fields


def test_description_brief_orders_verified_facts_without_filling_gaps() -> None:
    item = product(
        code="WW77#",
        item_name="Vestido feminino",
        ncm="6204.43.00",
        composition="100% poliéster",
        construction="tecido plano",
        color="rosa",
    )

    brief = build_description_preparation(item)

    assert brief.verified_facts == {
        "item_name": "Vestido feminino",
        "composition": "100% poliéster",
        "construction": "tecido plano",
        "color": "rosa",
        "code": "WW77#",
    }
    assert brief.ordered_fields == list(brief.verified_facts)
    assert "purpose" not in brief.verified_facts
    assert brief.missing_fields == []


def test_query_builder_uses_only_deterministic_multilingual_normalization() -> None:
    item = product(
        code="Y7052#",
        item_name="女装上衣",
        ncm="6206.40.00",
        composition="95%涤纶 5%氨纶",
        construction="梭织",
        manufacturer="戴一",
    )

    preparation = build_research_preparation(item)

    assert preparation.queries == [
        '"Y7052#"',
        '"Y7052#" "women\'s top"',
        '"Y7052#" "戴一"',
        '"Y7052#" "woven polyester elastane"',
    ]


def test_missing_identity_produces_review_warning_instead_of_query() -> None:
    item = product(item_name=None, code=None, composition="material plástico")

    preparation = build_research_preparation(item)

    assert preparation.queries == []
    assert preparation.missing_fields == ["item_name", "purpose"]
    assert preparation.warnings == [
        "Código/modelo ausente; a pesquisa exige revisão e pode ter baixa precisão.",
        "Não há evidência textual suficiente para formar uma consulta segura.",
    ]
