from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any


IGNORED_TAGS = {"style", "nav", "footer", "aside", "form", "svg", "noscript", "template"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
NOISE_MARKERS = {"cookie", "consent", "banner", "menu", "navigation", "footer", "popup", "modal"}
STRUCTURED_FIELDS = {
    "name", "sku", "mpn", "brand", "manufacturer", "model", "description",
    "material", "color", "category", "gtin", "gtin8", "gtin12", "gtin13",
    "gtin14", "url", "offers",
}


def _clean(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


class UsefulHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.meta_description: str | None = None
        self.headings: list[str] = []
        self.text_parts: list[str] = []
        self.json_ld_blocks: list[str] = []
        self._ignored_depth = 0
        self._title_depth = 0
        self._heading_depth = 0
        self._heading_parts: list[str] = []
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if self._ignored_depth:
            if tag not in VOID_TAGS:
                self._ignored_depth += 1
            return
        if tag == "meta" and attributes.get("name", "").casefold() in {"description", "og:description"}:
            if not self.meta_description and attributes.get("content"):
                self.meta_description = _clean(attributes["content"], 1000)
        if tag == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._json_ld_depth += 1
            self._json_ld_parts = []
            return
        marker_text = f"{attributes.get('id', '')} {attributes.get('class', '')}".casefold()
        noisy = any(marker in marker_text for marker in NOISE_MARKERS)
        if tag in IGNORED_TAGS or tag == "script" or noisy:
            self._ignored_depth += 1
            return
        if tag == "title":
            self._title_depth += 1
        if tag in {"h1", "h2"}:
            self._heading_depth += 1
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "script" and self._json_ld_depth:
            block = "".join(self._json_ld_parts).strip()
            if block:
                self.json_ld_blocks.append(block)
            self._json_ld_depth -= 1
            self._json_ld_parts = []
            return
        if self._ignored_depth:
            if tag not in VOID_TAGS:
                self._ignored_depth -= 1
            return
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"h1", "h2"} and self._heading_depth:
            heading = _clean(" ".join(self._heading_parts), 300)
            if heading and heading not in self.headings and len(self.headings) < 20:
                self.headings.append(heading)
            self._heading_depth -= 1
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_parts.append(data)
            return
        if self._ignored_depth:
            return
        cleaned = _clean(data, 2000)
        if not cleaned:
            return
        if self._title_depth:
            self.title_parts.append(cleaned)
        if self._heading_depth:
            self._heading_parts.append(cleaned)
        self.text_parts.append(cleaned)


def _type_names(value: Any) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {str(item).rsplit("/", 1)[-1].casefold() for item in values if item}


def _simple_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _clean(str(value.get("name") or value.get("value") or value.get("url") or ""), 2000)
    if isinstance(value, list):
        items = [_simple_value(item) for item in value[:20]]
        return [item for item in items if item not in {"", None}]
    if isinstance(value, (str, int, float, bool)):
        return _clean(str(value), 2000)
    return None


def _walk_json_ld(value: Any, output: list[dict]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_json_ld(item, output)
        return
    if not isinstance(value, dict):
        return
    types = _type_names(value.get("@type"))
    if types & {"product", "offer", "brand", "organization"}:
        item: dict[str, Any] = {"types": sorted(types)}
        for field in STRUCTURED_FIELDS:
            if field in value:
                simple = _simple_value(value[field])
                if simple is not None and simple != "" and simple != []:
                    item[field] = simple
        if len(item) > 1:
            output.append(item)
    for key in ("@graph", "mainEntity", "itemListElement", "offers", "brand", "manufacturer"):
        if key in value:
            _walk_json_ld(value[key], output)


def extract_html(html: str) -> dict[str, Any]:
    parser = UsefulHTMLParser()
    parser.feed(html)
    parser.close()
    structured: list[dict] = []
    for block in parser.json_ld_blocks[:20]:
        try:
            _walk_json_ld(json.loads(block), structured)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    text = _clean(" ".join(parser.text_parts), 12_000)
    return {
        "title": _clean(" ".join(parser.title_parts), 500) or None,
        "meta_description": parser.meta_description,
        "headings": parser.headings,
        "text": text,
        "text_excerpt": text[:4000],
        "structured_data": {"items": structured[:20]},
    }
