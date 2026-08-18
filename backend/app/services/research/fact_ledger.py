"""Construtor determinístico do Fact Ledger para geração DUIMP.

Transforma o resultado consolidado do labels_multimodal em um ledger
estruturado de fatos com status CONFIRMED/CONFLICTING/UNKNOWN/UNCERTAIN.
Somente fatos CONFIRMED alimentam a descrição técnica.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.research.duimp_schemas import (
    CompositionLayer,
    ExcludedField,
    FactEntry,
    FactLedger,
)

# Normalizações determinísticas inequívocas
_FIBER_PT: dict[str, str] = {
    "polyester": "poli\u00e9ster",
    "elastane": "elastano",
    "cotton": "algod\u00e3o",
    "nylon": "nylon",
    "silk": "seda",
    "wool": "l\u00e3",
    "linen": "linho",
    "viscose": "viscose",
    "rayon": "raiom",
}

_CHINESE_FIBER_PT: dict[str, str] = {
    "\u6da4": "poli\u00e9ster",
    "\u6da4\u7eb6": "poli\u00e9ster",
    "\u68c9": "algod\u00e3o",
    "\u6c28\u7eb6": "elastano",
    "\u9526\u7eb6": "nylon",
    "\u4e1d": "seda",
    "\u6bdb": "l\u00e3",
    "\u9ebb": "linho",
    "\u7c98\u7ea4": "viscose",
}

_PACKING_COMP_RE = re.compile(
    r"(\d+)\s*%?\s*"
    r"(\u6da4\u7eb6|\u6da4|\u68c9|\u6c28\u7eb6|\u9526\u7eb6|\u4e1d|\u6bdb|\u9ebb|\u7c98\u7ea4|PU|pu|spandex)",
    re.IGNORECASE,
)

_LAYER_SPLIT_RE = re.compile(r"[+＋]")

_CONSTRUCTION_PT: dict[str, str] = {
    "woven": "tecido plano",
    "knitted": "malha",
    "\u68ad\u7ec7": "tecido plano",
    "\u9488\u7ec7": "malha",
}

_CATEGORY_PT: dict[str, str] = {
    "dress": "vestido",
    "shirt": "camisa",
    "blouse": "blusa",
    "pants": "cal\u00e7a",
    "skirt": "saia",
    "jacket": "jaqueta",
    "coat": "casaco",
    "shorts": "bermuda",
    "top": "top",
}

_ITEM_NAME_PT: dict[str, str] = {
    "\u8fde\u8863\u88d9": "vestido",
    "\u886c\u886b": "camisa",
    "\u4e0a\u8863": "blusa",
    "\u88e4\u5b50": "cal\u00e7a",
    "\u957f\u88e4": "cal\u00e7a",
    "\u5957\u88c5": "conjunto",
    "\u534a\u8eab\u88d9": "saia",
    "\u77ed\u88e4": "bermuda",
    "\u5916\u5957": "casaco",
}


def _normalize_fiber(fiber: str) -> str:
    return _FIBER_PT.get(fiber.lower(), fiber.lower())


def _normalize_chinese_fiber(fiber: str) -> str:
    low = fiber.strip().lower()
    if low in ("pu", "spandex"):
        return low.upper() if low == "pu" else "elastano"
    return _CHINESE_FIBER_PT.get(fiber.strip(), fiber.strip())


def _parse_packing_composition(
    raw: str,
    evidence_ids: list[str],
) -> tuple[list[CompositionLayer], str]:
    """Tenta parse determinístico de composição em string de packing list.

    Suporta padrões como:
    - "100涤" → 100% poliéster
    - "95棉5氨纶+100pu" → 2 camadas
    - "95%涤纶 5%氨纶" → camada única com 2 fibras

    Retorna ([], "UNKNOWN") se não conseguir parsear com segurança.
    """
    if not raw or not raw.strip():
        return [], "UNKNOWN"

    text = raw.strip()
    layer_parts = _LAYER_SPLIT_RE.split(text)

    layers: list[CompositionLayer] = []
    for idx, part in enumerate(layer_parts):
        matches = _PACKING_COMP_RE.findall(part)
        if not matches:
            return [], "UNKNOWN"

        fibers = []
        total = 0
        for pct_str, fiber_raw in matches:
            pct = int(pct_str)
            total += pct
            normalized = _normalize_chinese_fiber(fiber_raw)
            fibers.append({
                "fiber": normalized,
                "fiber_original": fiber_raw,
                "percentage": pct,
            })

        if total > 100:
            return [], "UNKNOWN"

        layer_name = "main" if len(layer_parts) == 1 else f"layer_{idx + 1}"
        layers.append(CompositionLayer(
            layer_name=layer_name,
            fibers=fibers,
            status="CONFIRMED",
            evidence_ids=evidence_ids,
        ))

    if not layers:
        return [], "UNKNOWN"

    return layers, "CONFIRMED"


def _normalize_construction(value: str) -> str:
    return _CONSTRUCTION_PT.get(value.strip(), value.strip())


def _normalize_category(value: str) -> str:
    return _CATEGORY_PT.get(value.lower().strip(), value.lower().strip())


def _normalize_item_name(value: str) -> str:
    stripped = value.strip()
    exact = _ITEM_NAME_PT.get(stripped)
    if exact:
        return exact
    for cn_key, pt_val in _ITEM_NAME_PT.items():
        if cn_key in stripped:
            return pt_val
    return stripped


def _make_entry(
    value: Any,
    status: str,
    evidence_ids: list[str] | None = None,
    source_types: list[str] | None = None,
) -> FactEntry:
    return FactEntry(
        value=value,
        status=status,
        evidence_ids=evidence_ids or [],
        source_types=source_types or [],
    )


def _unknown_entry() -> FactEntry:
    return _make_entry(None, "UNKNOWN")


def build_fact_ledger(
    labels_result: dict[str, Any],
    wash_evidence: dict[str, Any] | None = None,
    hangtag_evidence: dict[str, Any] | None = None,
    visual_evidence: dict[str, Any] | None = None,
) -> FactLedger:
    """Constrói o Fact Ledger a partir do resultado labels_multimodal e evidências brutas."""

    confirmed = {
        cf["field"]: cf for cf in labels_result.get("confirmed_fields", [])
    }
    conflicts_raw = labels_result.get("conflicts", [])
    conflict_fields = {c["field"] for c in conflicts_raw}
    unknown_fields = set(labels_result.get("unknown_fields", []))

    # --- product_code ---
    product_code = _resolve(confirmed, "code", conflict_fields)

    # --- item_name ---
    raw_item = _resolve(confirmed, "item_name", conflict_fields)
    if raw_item.status == "CONFIRMED" and raw_item.value:
        normalized = _normalize_item_name(str(raw_item.value))
        item_name = _make_entry(
            normalized, raw_item.status, raw_item.evidence_ids, raw_item.source_types
        )
    else:
        item_name = raw_item

    # --- category ---
    raw_cat = _resolve(confirmed, "category_visual", conflict_fields)
    if raw_cat.status == "CONFIRMED" and raw_cat.value:
        normalized = _normalize_category(str(raw_cat.value))
        category = _make_entry(
            normalized, raw_cat.status, raw_cat.evidence_ids, raw_cat.source_types
        )
    else:
        category = raw_cat

    # --- ncm ---
    ncm = _resolve(confirmed, "ncm", conflict_fields)

    # --- construction ---
    raw_cons = _resolve(confirmed, "construction", conflict_fields)
    if raw_cons.status == "CONFIRMED" and raw_cons.value:
        normalized = _normalize_construction(str(raw_cons.value))
        construction = _make_entry(
            normalized, raw_cons.status, raw_cons.evidence_ids, raw_cons.source_types
        )
    else:
        construction = raw_cons

    # --- manufacturer ---
    manufacturer = _resolve(confirmed, "manufacturer", conflict_fields)

    # --- brand (separate from manufacturer) ---
    brand = _resolve(confirmed, "brand", conflict_fields)

    # --- country_of_origin ---
    country_of_origin = _resolve(confirmed, "country_of_origin", conflict_fields)

    # --- size ---
    size = _resolve_or_unknown(confirmed, "size", unknown_fields, conflict_fields)

    # --- primary_color ---
    primary_color = _resolve(confirmed, "primary_color", conflict_fields)

    # --- sleeves / straps (ambiguity check) ---
    sleeves_raw = _resolve(confirmed, "sleeves", conflict_fields)
    straps_raw = _resolve_or_unknown(confirmed, "straps", unknown_fields, conflict_fields)
    # If sleeves has uncertain_attributes from visual, mark UNCERTAIN
    sleeves = _check_sleeves_straps_ambiguity(sleeves_raw, visual_evidence)
    straps = _check_sleeves_straps_ambiguity(straps_raw, visual_evidence)

    # --- length ---
    length = _resolve(confirmed, "length", conflict_fields)

    # --- visible_details ---
    visible_details = _resolve(confirmed, "visible_details", conflict_fields)

    # --- composition layers ---
    comp_layers, comp_status, comp_evidence_ids = _build_composition(
        confirmed, wash_evidence, conflicts_raw, conflict_fields
    )

    return FactLedger(
        product_code=product_code,
        item_name=item_name,
        category=category,
        ncm=ncm,
        construction=construction,
        manufacturer=manufacturer,
        brand=brand,
        country_of_origin=country_of_origin,
        size=size,
        primary_color=primary_color,
        sleeves=sleeves,
        straps=straps,
        length=length,
        visible_details=visible_details,
        composition_layers=comp_layers,
        composition_status=comp_status,
        composition_evidence_ids=comp_evidence_ids,
    )


def _resolve(
    confirmed: dict[str, dict],
    field: str,
    conflict_fields: set[str],
) -> FactEntry:
    if field in conflict_fields:
        return _make_entry(None, "CONFLICTING")
    cf = confirmed.get(field)
    if cf and cf.get("value"):
        return _make_entry(
            cf["value"], "CONFIRMED",
            cf.get("evidence_ids", []),
            cf.get("source_types", []),
        )
    return _unknown_entry()


def _resolve_or_unknown(
    confirmed: dict[str, dict],
    field: str,
    unknown_fields: set[str],
    conflict_fields: set[str],
) -> FactEntry:
    if field in conflict_fields:
        return _make_entry(None, "CONFLICTING")
    if field in unknown_fields:
        return _unknown_entry()
    cf = confirmed.get(field)
    if cf and cf.get("value"):
        return _make_entry(
            cf["value"], "CONFIRMED",
            cf.get("evidence_ids", []),
            cf.get("source_types", []),
        )
    return _unknown_entry()


def _check_sleeves_straps_ambiguity(
    entry: FactEntry,
    visual_evidence: dict[str, Any] | None,
) -> FactEntry:
    """Se mangas/alças estiverem em uncertain_attributes, marcar UNCERTAIN."""
    if entry.status != "CONFIRMED":
        return entry
    if not visual_evidence:
        return entry
    uncertain = visual_evidence.get("uncertain_attributes", [])
    for ua in uncertain:
        if ua.get("field") in ("sleeves", "straps"):
            return _make_entry(
                entry.value, "UNCERTAIN",
                entry.evidence_ids, entry.source_types,
            )
    return entry


def _build_composition(
    confirmed: dict[str, dict],
    wash_evidence: dict[str, Any] | None,
    conflicts_raw: list[dict],
    conflict_fields: set[str],
) -> tuple[list[CompositionLayer], str, list[str]]:
    """Constrói camadas de composição.

    Prioridade: wash label > packing list composition.
    Se a composição estiver em conflito material, retorna status CONFLICTING.
    """
    evidence_ids: list[str] = []

    if "composition" in conflict_fields:
        comp_conflict = next(
            (c for c in conflicts_raw if c["field"] == "composition"), None
        )
        if comp_conflict:
            sources = comp_conflict.get("sources", [])
            if _is_format_conflict(sources):
                if wash_evidence and wash_evidence.get("status") == "OK":
                    return _layers_from_wash(wash_evidence, "CONFIRMED")
                return [], "CONFLICTING", evidence_ids
            else:
                return [], "CONFLICTING", evidence_ids

    if wash_evidence and wash_evidence.get("status") == "OK":
        return _layers_from_wash(wash_evidence, "CONFIRMED")

    # Fallback: composição como string na packing list
    comp_cf = confirmed.get("composition")
    if comp_cf and comp_cf.get("value"):
        raw_comp = str(comp_cf["value"])
        comp_eids = comp_cf.get("evidence_ids", ["PACKING-001"])
        layers, status = _parse_packing_composition(raw_comp, comp_eids)
        if status == "CONFIRMED" and layers:
            return layers, status, comp_eids

    return [], "UNKNOWN", evidence_ids


def _is_format_conflict(sources: list[dict]) -> bool:
    """Determina se o conflito é apenas de representação (idioma/formato)."""
    values = [s.get("value", "") for s in sources]
    # Heuristic: if both contain polyester-related terms, it's format-only
    has_poly = all(
        any(t in v.lower() for t in ("poly", "涤", "poli"))
        for v in values if v
    )
    return has_poly


def _layers_from_wash(
    wash: dict[str, Any],
    status: str,
) -> tuple[list[CompositionLayer], str, list[str]]:
    """Extrai camadas de composição da wash label evidence."""
    evidence_ids = ["WASH-001"]
    raw_texts = [t["text"] for t in wash.get("raw_visible_text", [])]
    composition = wash.get("composition", [])

    # Detect layers from raw text
    has_exterior = any("EXTERIOR" in t.upper() or "OUTER" in t.upper() for t in raw_texts)
    has_interior = any("INTERIOR" in t.upper() or "INNER" in t.upper() or "LINING" in t.upper() for t in raw_texts)

    layers: list[CompositionLayer] = []

    if has_exterior and has_interior and len(composition) >= 3:
        # Two-layer composition: first fiber is exterior, rest is interior
        exterior_fiber = composition[0]
        interior_fibers = composition[1:]

        layers.append(CompositionLayer(
            layer_name="exterior",
            fibers=[{
                "fiber": _normalize_fiber(exterior_fiber.get("fiber_normalized", "")),
                "fiber_original": exterior_fiber.get("fiber_original", ""),
                "percentage": exterior_fiber.get("percentage"),
            }],
            status=status,
            evidence_ids=evidence_ids,
        ))
        layers.append(CompositionLayer(
            layer_name="interior",
            fibers=[{
                "fiber": _normalize_fiber(f.get("fiber_normalized", "")),
                "fiber_original": f.get("fiber_original", ""),
                "percentage": f.get("percentage"),
            } for f in interior_fibers],
            status=status,
            evidence_ids=evidence_ids,
        ))
    elif composition:
        # Single layer
        layers.append(CompositionLayer(
            layer_name="main",
            fibers=[{
                "fiber": _normalize_fiber(f.get("fiber_normalized", "")),
                "fiber_original": f.get("fiber_original", ""),
                "percentage": f.get("percentage"),
            } for f in composition],
            status=status,
            evidence_ids=evidence_ids,
        ))

    return layers, status, evidence_ids


def get_excluded_fields(ledger: FactLedger) -> list[ExcludedField]:
    """Retorna campos excluídos da descrição com motivo."""
    excluded: list[ExcludedField] = []

    field_map = {
        "item_name": ledger.item_name,
        "category": ledger.category,
        "ncm": ledger.ncm,
        "construction": ledger.construction,
        "manufacturer": ledger.manufacturer,
        "brand": ledger.brand,
        "country_of_origin": ledger.country_of_origin,
        "size": ledger.size,
        "primary_color": ledger.primary_color,
        "sleeves": ledger.sleeves,
        "straps": ledger.straps,
        "length": ledger.length,
        "visible_details": ledger.visible_details,
    }

    for field, entry in field_map.items():
        if entry.status != "CONFIRMED":
            excluded.append(ExcludedField(field=field, reason=entry.status))

    if ledger.composition_status != "CONFIRMED":
        excluded.append(ExcludedField(
            field="composition",
            reason=ledger.composition_status,
        ))

    return excluded


def get_confirmed_facts_summary(ledger: FactLedger) -> dict[str, Any]:
    """Retorna resumo dos fatos CONFIRMED para envio ao LLM."""
    facts: dict[str, Any] = {}

    field_map = {
        "product_code": ledger.product_code,
        "item_name": ledger.item_name,
        "category": ledger.category,
        "ncm": ledger.ncm,
        "construction": ledger.construction,
        "manufacturer": ledger.manufacturer,
        "brand": ledger.brand,
        "country_of_origin": ledger.country_of_origin,
        "size": ledger.size,
        "primary_color": ledger.primary_color,
        "sleeves": ledger.sleeves,
        "straps": ledger.straps,
        "length": ledger.length,
        "visible_details": ledger.visible_details,
    }

    for field, entry in field_map.items():
        if entry.status == "CONFIRMED":
            facts[field] = {
                "value": entry.value,
                "evidence_ids": entry.evidence_ids,
            }

    if ledger.composition_status == "CONFIRMED":
        facts["composition"] = {
            "layers": [
                {
                    "layer": layer.layer_name,
                    "fibers": layer.fibers,
                }
                for layer in ledger.composition_layers
            ],
            "evidence_ids": ledger.composition_evidence_ids,
        }

    return facts
