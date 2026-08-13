from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.research.fetch_cache import FetchCache
from app.services.research.html_extract import extract_html
from app.services.research.schemas import EnrichedWebEvidence


logger = logging.getLogger(__name__)
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
MAX_REDIRECTS = 3
USER_AGENT = "ProjetoDigitacao-EvidenceFetcher/1.0 (+controlled research; contact: local operator)"


class SSRFBlockedError(ValueError):
    pass


def _is_forbidden_ip(value: str) -> bool:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    return not address.is_global


def _system_resolver(host: str, port: int) -> list[str]:
    return list({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})


async def validate_public_url(
    url: str,
    resolver: Callable[[str, int], list[str]] = _system_resolver,
) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise SSRFBlockedError("URL inválida") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SSRFBlockedError("Esquema ou host não permitido")
    if parsed.username or parsed.password:
        raise SSRFBlockedError("Credenciais embutidas não são permitidas")
    expected_port = 443 if parsed.scheme == "https" else 80
    if port not in {None, expected_port}:
        raise SSRFBlockedError("Porta não permitida")
    host = parsed.hostname.rstrip(".").casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise SSRFBlockedError("Host interno não permitido")
    try:
        addresses = [host] if ipaddress.ip_address(host) else []
    except ValueError:
        try:
            addresses = await asyncio.to_thread(resolver, host, expected_port)
        except OSError as exc:
            raise SSRFBlockedError("Host não pôde ser resolvido com segurança") from exc
    if not addresses or any(_is_forbidden_ip(address) for address in addresses):
        raise SSRFBlockedError("Destino interno ou não público bloqueado")


class ControlledFetcher:
    def __init__(
        self,
        *,
        cache: FetchCache,
        timeout_seconds: float,
        max_bytes: int,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Callable[[str, int], list[str]] = _system_resolver,
    ) -> None:
        self.cache = cache
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.transport = transport
        self.resolver = resolver

    def _result(self, url: str, status: str, started: float, **values: object) -> EnrichedWebEvidence:
        final_url = str(values.pop("final_url", url))
        return EnrichedWebEvidence(
            url=url,
            final_url=final_url,
            domain=(urlsplit(final_url).hostname or "").casefold(),
            fetch_status=status,
            fetched_at=datetime.now(UTC),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            **values,
        )

    def _persist(self, url: str, result: EnrichedWebEvidence) -> EnrichedWebEvidence:
        try:
            self.cache.put(url, result.model_dump(mode="json"))
        except OSError as exc:
            logger.warning("Não foi possível persistir cache de fetch: %s", type(exc).__name__)
        return result

    async def fetch(self, url: str, *, refresh_cache: bool = False) -> EnrichedWebEvidence:
        started = time.monotonic()
        try:
            await validate_public_url(url, self.resolver)
        except SSRFBlockedError as exc:
            return self._result(url, "SSRF_BLOCKED", started, error=str(exc))
        lookup = self.cache.get(url)
        if not refresh_cache and lookup.payload is not None and lookup.status == "HIT":
            cached = EnrichedWebEvidence.model_validate(lookup.payload)
            cached.cache_status = "HIT"
            return cached
        cache_status = "EXPIRED" if lookup.status == "EXPIRED" else "MISS"
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9",
            "Accept-Encoding": "gzip, br",
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        current_url = url
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                verify=True,
                headers=headers,
                transport=self.transport,
            ) as client:
                for redirect_count in range(MAX_REDIRECTS + 1):
                    await validate_public_url(current_url, self.resolver)
                    async with client.stream("GET", current_url) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location or redirect_count == MAX_REDIRECTS:
                                return self._result(
                                    url, "HTTP_ERROR", started, final_url=current_url,
                                    http_status=response.status_code, cache_status=cache_status,
                                    error="Limite de redirects excedido.",
                                )
                            current_url = urljoin(current_url, location)
                            await validate_public_url(current_url, self.resolver)
                            continue
                        if response.status_code in {401, 403, 407, 429}:
                            return self._persist(url, self._result(
                                url, "BLOCKED", started, final_url=current_url,
                                http_status=response.status_code, cache_status=cache_status,
                            ))
                        if response.status_code < 200 or response.status_code >= 300:
                            return self._result(
                                url, "HTTP_ERROR", started, final_url=current_url,
                                http_status=response.status_code, cache_status=cache_status,
                            )
                        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
                        if content_type not in ALLOWED_CONTENT_TYPES:
                            return self._persist(url, self._result(
                                url, "UNSUPPORTED_CONTENT", started, final_url=current_url,
                                http_status=response.status_code, content_type=content_type or None,
                                cache_status=cache_status,
                            ))
                        length = response.headers.get("content-length")
                        if length and length.isdigit() and int(length) > self.max_bytes:
                            return self._persist(url, self._result(
                                url, "TOO_LARGE", started, final_url=current_url,
                                http_status=response.status_code, content_type=content_type,
                                cache_status=cache_status,
                            ))
                        chunks: list[bytes] = []
                        downloaded = 0
                        async for chunk in response.aiter_bytes():
                            downloaded += len(chunk)
                            if downloaded > self.max_bytes:
                                return self._persist(url, self._result(
                                    url, "TOO_LARGE", started, final_url=current_url,
                                    http_status=response.status_code, content_type=content_type,
                                    bytes_downloaded=downloaded, cache_status=cache_status,
                                ))
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        charset = response.encoding or "utf-8"
                        try:
                            html = body.decode(charset, errors="replace")
                        except LookupError:
                            html = body.decode("utf-8", errors="replace")
                        try:
                            extracted = extract_html(html)
                        except Exception as exc:
                            logger.warning("Falha ao extrair HTML do domínio %s: %s", urlsplit(current_url).hostname, type(exc).__name__)
                            return self._result(
                                url, "PARSE_ERROR", started, final_url=current_url,
                                http_status=response.status_code, content_type=content_type,
                                bytes_downloaded=downloaded, cache_status=cache_status,
                            )
                        result = self._result(
                            url, "OK", started, final_url=current_url,
                            http_status=response.status_code, content_type=content_type,
                            title=extracted["title"], meta_description=extracted["meta_description"],
                            headings=extracted["headings"], text_excerpt=extracted["text_excerpt"],
                            structured_data=extracted["structured_data"],
                            content_hash=hashlib.sha256(body).hexdigest(),
                            bytes_downloaded=downloaded, cache_status=cache_status,
                        )
                        self._persist(url, result)
                        logger.info(
                            "Fetch controlado concluído (domínio=%s, status=%s, bytes=%s)",
                            result.domain, result.http_status, downloaded,
                        )
                        return result
        except SSRFBlockedError as exc:
            return self._result(url, "SSRF_BLOCKED", started, final_url=current_url, cache_status=cache_status, error=str(exc))
        except httpx.TimeoutException:
            return self._result(url, "TIMEOUT", started, final_url=current_url, cache_status=cache_status)
        except httpx.HTTPError as exc:
            logger.info("Fetch falhou (domínio=%s, erro=%s)", urlsplit(current_url).hostname, type(exc).__name__)
            return self._result(url, "HTTP_ERROR", started, final_url=current_url, cache_status=cache_status)
