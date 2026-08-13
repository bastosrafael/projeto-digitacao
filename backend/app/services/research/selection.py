from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.spreadsheets.schemas import Product


RICH_FIELDS = (
    "code", "item_name", "composition", "construction", "manufacturer", "supplier",
    "brand", "purpose", "ncm", "dimensions", "weight", "capacity", "voltage", "power",
    "frequency", "battery", "recharge", "connection", "accessories", "color", "size",
)
FIELD_WEIGHTS = {
    "code": 4, "item_name": 3, "composition": 3, "construction": 2,
    "manufacturer": 3, "supplier": 3, "brand": 3, "purpose": 2, "ncm": 1,
}
DIVERSITY_FIELDS = ("item_name", "composition", "construction", "manufacturer", "supplier", "brand", "ncm")


@dataclass(frozen=True)
class ProductSelection:
    product: Product
    richness_score: int
    available_fields: tuple[str, ...]
    reasons: tuple[str, ...]


def _usable(value: str | None) -> bool:
    cleaned = (value or "").strip()
    return bool(cleaned and not cleaned.startswith("=DISPIMG("))


def _richness(product: Product) -> tuple[int, tuple[str, ...]]:
    fields = tuple(field for field in RICH_FIELDS if _usable(getattr(product, field)))
    score = sum(FIELD_WEIGHTS.get(field, 1) for field in fields)
    # Códigos longos/estruturados tendem a ser menos ambíguos na busca pública.
    compact_code = re.sub(r"\W", "", product.code or "")
    score += min(3, max(0, len(compact_code) - 5))
    return score, fields


def select_rich_products(products: list[Product], limit: int = 3) -> list[ProductSelection]:
    candidates = []
    for index, product in enumerate(products):
        score, fields = _richness(product)
        if product.code and product.item_name and product.research_preparation.queries:
            candidates.append((product, score, fields, index))
    selected: list[ProductSelection] = []
    seen_values: set[tuple[str, str]] = set()
    while candidates and len(selected) < limit:
        def rank(candidate: tuple[Product, int, tuple[str, ...], int]) -> tuple[int, int, int, int]:
            product, score, fields, index = candidate
            novelty = sum(
                (field, str(getattr(product, field)).casefold()) not in seen_values
                for field in DIVERSITY_FIELDS
                if _usable(getattr(product, field))
            )
            return len(fields), novelty, score, -index

        product, score, fields, _ = max(candidates, key=rank)
        candidates = [candidate for candidate in candidates if candidate[0] is not product]
        novelty_fields = [
            field for field in DIVERSITY_FIELDS
            if _usable(getattr(product, field))
            and (field, str(getattr(product, field)).casefold()) not in seen_values
        ]
        for field in DIVERSITY_FIELDS:
            if _usable(getattr(product, field)):
                seen_values.add((field, str(getattr(product, field)).casefold()))
        selected.append(ProductSelection(
            product=product,
            richness_score=score,
            available_fields=fields,
            reasons=(
                f"{len(fields)} campos textuais úteis",
                f"score de riqueza {score}",
                f"diversidade adicional em: {', '.join(novelty_fields) or 'nenhum campo'}",
            ),
        ))
    return selected
