from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "image": ("picture", "product picture", "product image", "image", "photo", "图片", "照片"),
    "code": (
        "style number", "style no", "style", "code", "codigo", "product code",
        "item code", "item no", "sku", "reference", "ref", "model", "modelo", "款号", "货号",
    ),
    "ncm": ("ncm",),
    "item_name": ("item name", "product name", "item", "produto", "nome do produto", "品名", "产品名称"),
    "composition": (
        "ingredients", "composition", "fabric content", "material", "composicao", "成份", "成分", "面料",
    ),
    "construction": ("construction", "woven", "knitted", "weaving", "tecelagem", "织造方式", "织法"),
    "color": ("color", "colour", "cor", "颜色"),
    "size": ("size", "tamanho", "尺码"),
    "manufacturer": ("manufacturer", "factory", "fabricante", "厂家", "制造商"),
    "supplier": ("supplier", "fornecedor", "供应商"),
    "brand": ("brand", "marca", "品牌"),
    "wash_label": ("wash label", "washing label", "care label", "etiqueta de lavagem", "洗水唛", "洗标"),
    "hangtag": ("hangtag", "hang tag", "吊牌"),
    "label": ("label", "etiqueta", "标签"),
    "packing_info": ("packing info", "carton number", "carton", "box", "caixa", "箱号", "箱数", "箱规"),
}

NCM_PATTERN = re.compile(r"^\d{4}(?:[.\s-]?\d{2}){2}$")
CODE_PATTERN = re.compile(r"^[A-Z0-9#]+(?:[-_/][A-Z0-9#]+)*$", re.IGNORECASE)


def clean_text(value: object | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized_header(value: object | None) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    text = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
    text = re.sub(r"[^\w\u3400-\u9fff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


NORMALIZED_ALIASES = {
    role: tuple(normalized_header(alias) for alias in aliases)
    for role, aliases in HEADER_ALIASES.items()
}


def header_role(value: object | None) -> tuple[str | None, float]:
    text = normalized_header(value)
    if not text:
        return None, 0.0
    best_role = None
    best_score = 0.0
    for role, aliases in NORMALIZED_ALIASES.items():
        for alias in aliases:
            if text == alias:
                score = 1.0
            elif (
                len(alias) >= 3
                and (" " in alias or (re.search(r"[\u3400-\u9fff]", text) and re.search(r"[a-z]", text)))
                and re.search(rf"(?:^| ){re.escape(alias)}(?: |$)", text)
            ):
                score = 0.94
            elif len(text) >= 3 and text in alias:
                score = 0.78
            else:
                continue
            if score > best_score:
                best_role, best_score = role, score
    return best_role, best_score


def is_ncm(value: object | None) -> bool:
    return bool(NCM_PATTERN.fullmatch(clean_text(value)))


def is_code_candidate(value: object | None) -> bool:
    text = unicodedata.normalize("NFKC", clean_text(value)).upper()
    if not text or len(text) > 48 or is_ncm(text):
        return False
    if text in {"TOTAL", "SUBTOTAL", "合计", "RE", "PRIMEIRO", "N/A"}:
        return False
    prefix_match = re.match(r"^([A-Z0-9#]+(?:[-_/][A-Z0-9#]+)*)", text)
    if not prefix_match:
        return False
    first = prefix_match.group(1)
    remainder = text[len(first):].strip()
    if remainder and not (
        remainder.startswith(("(", "（"))
        or (re.fullmatch(r"[\u3400-\u9fff]+", remainder) and "箱" not in remainder)
    ):
        return False
    if not CODE_PATTERN.fullmatch(first):
        return False
    return any(char.isalpha() for char in first) or "#" in first


@dataclass(frozen=True)
class NormalizedCode:
    original: str
    normalized: str
    logistical_text: str | None


def normalize_code(value: object) -> NormalizedCode | None:
    original = clean_text(value)
    text = unicodedata.normalize("NFKC", original).strip()
    if not is_code_candidate(text):
        return None
    match = re.match(r"^([A-Za-z0-9#]+(?:[-_/][A-Za-z0-9#]+)*)(.*)$", text)
    if not match:
        return None
    prefix = match.group(1).upper()
    raw_suffix = match.group(2).strip()
    if raw_suffix and re.fullmatch(r"[\u3400-\u9fff]+", raw_suffix) and "箱" not in raw_suffix:
        return NormalizedCode(original=original, normalized=f"{prefix}{raw_suffix}", logistical_text=None)
    suffix = raw_suffix.strip(" -–—;:,()（）") or None
    return NormalizedCode(original=original, normalized=prefix, logistical_text=suffix)
