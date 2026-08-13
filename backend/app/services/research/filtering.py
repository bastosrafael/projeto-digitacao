from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.research.schemas import ResearchEvidence
from app.services.spreadsheets.schemas import Product


BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "pinterest.com", "tiktok.com", "youtube.com",
    "alldatasheet.com", "ww77.co",
}
MARKETPLACE_DOMAINS = {
    "alibaba.com", "aliexpress.com", "amazon.com", "amazon.com.br", "ebay.com",
    "mercadolivre.com.br", "shopee.com.br", "temu.com",
}
TRACKING_PARAMS = {"fbclid", "gclid", "ref", "source"}
NOISE_TERMS = {"casino", "betting", "porn", "torrent", "crack", "apk download", "slot online"}
STOPWORDS = {"para", "com", "uma", "the", "and", "product", "produto", "女士", "男装"}
SEARCH_PATH_PARTS = {"search", "buscar", "busca", "query", "results"}
SEARCH_QUERY_KEYS = {"q", "query", "search", "searchword", "keyword"}


@dataclass(frozen=True)
class ResultEvaluation:
    evidence: ResearchEvidence | None
    discard_reason: str | None
    canonical_url: str | None


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _domain_in(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def canonical_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    query = urlencode([
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_PARAMS
    ])
    host = parsed.hostname.casefold()
    if port:
        host = f"{host}:{port}"
    return urlunsplit((parsed.scheme.casefold(), host, parsed.path or "/", query, ""))


def _tokens(value: str | None) -> list[str]:
    return [
        token for token in re.findall(r"[\wÀ-ÿ%+-]{2,}", _fold(value or ""))
        if token not in STOPWORDS and not token.isdigit()
    ]


def _identity_matches_host(identity: str | None, host: str) -> bool:
    compact_identity = re.sub(r"[^a-z0-9]", "", _fold(identity or ""))
    compact_host = re.sub(r"[^a-z0-9]", "", _fold(host))
    return len(compact_identity) >= 4 and compact_identity in compact_host


def _source_category(host: str, url: str, product: Product) -> tuple[str, float, str | None]:
    # Compatibilidade nominal com o domínio é um sinal; não prova oficialidade.
    if _identity_matches_host(product.manufacturer or product.brand, host):
        return "MANUFACTURER", 1.5, "domínio compatível com fabricante/marca; oficialidade não confirmada"
    if _identity_matches_host(product.supplier, host):
        return "SUPPLIER", 1.25, "domínio compatível com fornecedor; oficialidade não confirmada"
    if _domain_in(host, MARKETPLACE_DOMAINS):
        return "MARKETPLACE", -0.5, "marketplace tratado como fonte secundária"
    folded_url = _fold(url)
    if any(term in host for term in ("distributor", "distribuidor")):
        return "DISTRIBUTOR", 0.25, "domínio identificado nominalmente como distribuidor"
    if any(term in folded_url for term in ("/shop/", "/store/", "loja")) or host.startswith("shop."):
        return "STORE", 0.0, "estrutura de URL compatível com loja"
    return "UNKNOWN", 0.0, None


def _is_internal_search_page(url: str) -> bool:
    parsed = urlsplit(url)
    parts = {part.casefold() for part in parsed.path.split("/") if part}
    keys = {key.casefold() for key, _ in parse_qsl(parsed.query)}
    return bool(parts & SEARCH_PATH_PARTS or keys & SEARCH_QUERY_KEYS)


def _query_echo(title: str, query: str, detail_signal_count: int) -> bool:
    if detail_signal_count:
        return False
    folded_title = _fold(title)
    parts = [
        part.strip('"') for part in re.findall(r'"[^"]+"|\S+', _fold(query))
        if len(part.strip('"')) >= 3
    ]
    return len(parts) >= 2 and sum(part in folded_title for part in parts) >= 2


def evaluate_result(raw: dict, product: Product, query: str, provider: str) -> ResultEvaluation:
    title = str(raw.get("title") or "").strip()
    snippet = str(raw.get("snippet") or raw.get("content") or "").strip()
    url = canonical_url(str(raw.get("url") or ""))
    if not title or not url:
        return ResultEvaluation(None, "invalid_result", url)
    host = _host(url)
    title_text = _fold(title)
    snippet_text = _fold(snippet)
    url_text = _fold(url)
    all_text = f"{title_text} {snippet_text} {url_text}"
    if _domain_in(host, BLOCKED_DOMAINS):
        return ResultEvaluation(None, "blocked_domain", url)
    if any(term in all_text for term in NOISE_TERMS):
        return ResultEvaluation(None, "spam_content", url)

    code = _fold(product.code or "").strip()
    compact_code = re.sub(r"\W", "", code)
    code_title = bool(compact_code and compact_code in re.sub(r"\W", "", title_text))
    code_snippet = bool(compact_code and compact_code in re.sub(r"\W", "", snippet_text))
    code_url = bool(compact_code and compact_code in re.sub(r"\W", "", url_text))
    score = 0.0
    reasons: list[str] = []
    if code_url:
        score += 6.0
        reasons.append("código/modelo presente na URL")
    elif code_snippet:
        score += 5.0
        reasons.append("código/modelo presente no snippet")
    elif code_title:
        score += 2.0
        reasons.append("código/modelo presente somente no título")

    detail_signals = 0
    corroborating_signals = 0
    item = _fold(product.item_name or "").strip()
    item_tokens = _tokens(product.item_name)
    item_all = bool(item and len(item) >= 3 and item in all_text)
    item_detail = bool(item and len(item) >= 3 and (item in snippet_text or item in url_text))
    matched_item_tokens = {token for token in item_tokens if token in all_text}
    matched_item_detail = {token for token in item_tokens if token in snippet_text or token in url_text}
    if item_all or matched_item_tokens:
        score += 2.0 if item_all else min(1.5, len(matched_item_tokens) * 0.6)
        corroborating_signals += 1
        reasons.append("categoria/nome do produto compatível")
    if item_detail or matched_item_detail:
        detail_signals += 1

    for label, value, weight in (
        ("marca", product.brand, 1.75),
        ("fabricante", product.manufacturer, 1.75),
        ("fornecedor", product.supplier, 1.5),
        ("composição", product.composition, 1.5),
        ("construção", product.construction, 1.0),
        ("NCM informada", product.ncm, 0.75),
    ):
        tokens = _tokens(value)
        if not tokens:
            continue
        matched_all = {token for token in tokens if token in all_text}
        matched_detail = {token for token in tokens if token in snippet_text or token in url_text}
        if matched_all:
            score += weight
            corroborating_signals += 1
            reasons.append(f"{label} compatível")
        if matched_detail:
            detail_signals += 1

    category, category_score, category_reason = _source_category(host, url, product)
    score += category_score
    if category_reason:
        reasons.append(category_reason)
    position = max(1, int(raw.get("position") or 1))
    score += max(0.0, 1.1 - position * 0.1)

    if _query_echo(title, query, detail_signals + int(code_snippet or code_url)):
        return ResultEvaluation(None, "query_echo", url)
    if _is_internal_search_page(url) and not (code_snippet or code_url):
        return ResultEvaluation(None, "internal_search_page", url)

    if (code_snippet or code_url) and not (len(compact_code) < 7 and corroborating_signals == 0):
        strength = "STRONG"
    elif code_title and (detail_signals or category in {"MANUFACTURER", "SUPPLIER"}):
        strength = "MODERATE"
    elif not code_title and detail_signals >= 2 and category in {"MANUFACTURER", "SUPPLIER"}:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    if strength == "WEAK":
        return ResultEvaluation(None, "weak_evidence", url)
    if not (code_title or code_snippet or code_url) and corroborating_signals < 2:
        return ResultEvaluation(None, "disconnected_content", url)
    if score < 4.0:
        return ResultEvaluation(None, "low_score", url)

    citation = raw.get("citation") if isinstance(raw.get("citation"), dict) else {}
    try:
        retrieved_at = datetime.fromisoformat(str(citation.get("retrieved_at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        retrieved_at = datetime.now(UTC)
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    evidence = ResearchEvidence(
        title=title[:500],
        url=url,
        snippet=snippet[:2000],
        provider=str(citation.get("provider") or provider),
        source_engine=str(metadata.get("source_type")) if metadata.get("source_type") else None,
        domain=host,
        source_category=category,
        evidence_strength=strength,
        position=position,
        retrieved_at=retrieved_at,
        query=query,
        score=round(score, 2),
        relevance_reasons=reasons,
    )
    return ResultEvaluation(evidence, None, url)


def score_result(raw: dict, product: Product, query: str, provider: str) -> ResearchEvidence | None:
    """Compatibilidade para chamadores que precisam somente da evidência aceita."""
    return evaluate_result(raw, product, query, provider).evidence
