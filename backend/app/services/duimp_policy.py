from __future__ import annotations

import re

from app.services.spreadsheets.schemas import (
    DescriptionPreparation,
    Product,
    ResearchPreparation,
)


POLICY_VERSION = "duimp-v1"

DESCRIPTION_FIELD_ORDER = (
    "item_name",
    "purpose",
    "composition",
    "construction",
    "dimensions",
    "weight",
    "capacity",
    "voltage",
    "power",
    "frequency",
    "battery",
    "recharge",
    "connection",
    "color",
    "size",
    "code",
    "brand",
    "manufacturer",
    "supplier",
    "accessories",
)

BASE_RESEARCH_FOCUS = ("natureza do produto", "função/finalidade", "material/composição")
APPAREL_FOCUS = (
    "tipo da peça e público, quando comprovado",
    "malha ou tecido plano",
    "composição percentual",
    "características construtivas relevantes",
)
ELECTRICAL_FOCUS = (
    "modo de funcionamento",
    "tensão, potência e frequência",
    "alimentação, bateria e recarga",
    "conexão e acessórios integrantes",
)
PART_FOCUS = (
    "equipamento ao qual se destina",
    "função da parte ou acessório",
    "material e características construtivas",
)

APPAREL_TERMS = {
    "camiseta",
    "t-shirt",
    "shirt",
    "vestido",
    "body",
    "top",
    "blusa",
    "calca",
    "calça",
    "saia",
    "short",
    "legging",
    "lenco",
    "lenço",
    "vestuario",
    "vestuário",
}
PART_TERMS = {
    "parte", "part", "peca", "peça", "acessorio", "acessório", "accessory",
    "adaptador", "adapter", "componente", "component",
}

# Glossário deliberadamente pequeno e determinístico. Ele cobre somente termos
# inequívocos observados nos Packing Lists; valores desconhecidos permanecem no
# idioma original e nunca são traduzidos por inferência ou IA.
PRODUCT_TERM_TRANSLATIONS = {
    "梭织吊带短裤套装": "women's woven camisole and shorts set",
    "梭织吊带长裤套装": "women's woven camisole and trousers set",
    "梭织女士套装": "women's woven set",
    "针织女士套装": "women's knitted set",
    "梭织女士上衣": "women's woven top",
    "针织女士上衣": "women's knitted top",
    "男款针织短裤": "men's knitted shorts",
    "针织男装上衣": "men's knitted top",
    "短袖T恤": "short sleeve T-shirt",
    "女装短裤": "women's shorts",
    "女装短裙": "women's skirt",
    "女装T恤": "women's T-shirt",
    "女装上衣": "women's top",
    "女士套装": "women's set",
    "连衣裙": "dress",
    "蝙蝠衫": "batwing top",
}
CONSTRUCTION_TRANSLATIONS = {"梭织": "woven", "针织": "knitted"}
FIBER_TRANSLATIONS = {
    "涤纶": "polyester",
    "涤": "polyester",
    "氨纶": "elastane",
    "棉": "cotton",
    "尼龙": "nylon",
}


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _quote(value: str) -> str:
    sanitized = _clean(value.replace('"', " "))[:160]
    return f'"{_clean(sanitized)}"'


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _normalized_product_term(value: str) -> str:
    cleaned = _clean(value)
    for source in sorted(PRODUCT_TERM_TRANSLATIONS, key=len, reverse=True):
        if source in cleaned:
            return PRODUCT_TERM_TRANSLATIONS[source]
    return cleaned


def _normalized_characteristics(product: Product) -> str:
    terms: list[str] = []
    construction = _clean(product.construction)
    if construction:
        terms.append(CONSTRUCTION_TRANSLATIONS.get(construction, construction))
    composition = _clean(product.composition)
    for source in sorted(FIBER_TRANSLATIONS, key=len, reverse=True):
        if source in composition:
            terms.append(FIBER_TRANSLATIONS[source])
            composition = composition.replace(source, " ")
    terms.extend(
        _clean(getattr(product, field))
        for field in ("connection", "voltage", "power", "dimensions")
        if _clean(getattr(product, field))
    )
    return " ".join(_unique(terms)[:3])


def _category_focus(product: Product) -> tuple[list[str], list[str]]:
    text = " ".join(filter(None, (product.item_name, product.purpose))).casefold()
    ncm_digits = re.sub(r"\D", "", product.ncm or "")
    words = set(re.findall(r"[\wÀ-ÿ-]+", text))
    if ncm_digits.startswith(("61", "62")) or words & APPAREL_TERMS:
        missing = [
            field
            for field in ("item_name", "composition", "construction")
            if not _clean(getattr(product, field))
        ]
        return list(BASE_RESEARCH_FOCUS + APPAREL_FOCUS), missing
    if words & PART_TERMS:
        missing = [
            field
            for field in ("item_name", "purpose", "composition")
            if not _clean(getattr(product, field))
        ]
        return list(BASE_RESEARCH_FOCUS + PART_FOCUS), missing
    if ncm_digits.startswith(("84", "85")) or any(
        _clean(getattr(product, field))
        for field in ("voltage", "power", "frequency", "battery", "recharge", "connection")
    ):
        missing = [
            field
            for field in ("item_name", "purpose", "voltage", "power")
            if not _clean(getattr(product, field))
        ]
        return list(BASE_RESEARCH_FOCUS + ELECTRICAL_FOCUS), missing
    missing = [field for field in ("item_name", "purpose", "composition") if not _clean(getattr(product, field))]
    return list(BASE_RESEARCH_FOCUS), missing


def build_research_preparation(product: Product) -> ResearchPreparation:
    evidence_terms = {
        field: value
        for field in ("code", "item_name", "ncm", *DESCRIPTION_FIELD_ORDER)
        if (value := _clean(getattr(product, field)))
    }
    identity = _clean(product.brand) or _clean(product.manufacturer) or _clean(product.supplier)
    code = _clean(product.code)
    item = _clean(product.item_name)
    ncm = _clean(product.ncm)
    safe_ncm = re.sub(r"\D", "", ncm)[:12]
    queries: list[str] = []
    if code:
        queries.append(_quote(code))
        category = _normalized_product_term(item) if item else ""
        if category:
            queries.append(f"{_quote(code)} {_quote(category)}")
        if identity:
            queries.append(f"{_quote(code)} {_quote(identity)}")
        characteristics = _normalized_characteristics(product)
        if characteristics:
            queries.append(f"{_quote(code)} {_quote(characteristics)}")
        elif safe_ncm:
            queries.append(f"{_quote(code)} {safe_ncm}")
    elif item:
        queries.append(_quote(_normalized_product_term(item)))

    focus, missing = _category_focus(product)
    warnings: list[str] = []
    if not code:
        warnings.append("Código/modelo ausente; a pesquisa exige revisão e pode ter baixa precisão.")
    if not queries:
        warnings.append("Não há evidência textual suficiente para formar uma consulta segura.")
    if ncm:
        warnings.append("A NCM da planilha é termo de pesquisa, não confirmação automática da classificação.")
    return ResearchPreparation(
        queries=_unique(queries),
        evidence_terms=evidence_terms,
        focus_fields=focus,
        missing_fields=_unique(missing),
        warnings=warnings,
    )


def build_description_preparation(product: Product) -> DescriptionPreparation:
    verified = {
        field: value
        for field in DESCRIPTION_FIELD_ORDER
        if (value := _clean(getattr(product, field)))
    }
    _, missing = _category_focus(product)
    return DescriptionPreparation(
        verified_facts=verified,
        ordered_fields=list(verified),
        missing_fields=_unique(missing),
        policy_version=POLICY_VERSION,
    )


def prepare_product(product: Product) -> None:
    product.research_preparation = build_research_preparation(product)
    product.description_preparation = build_description_preparation(product)
