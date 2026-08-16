"""Testes de fallback visual gratuito no OmniRouteService.complete_vision_json."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.services.omniroute import (
    OmniRouteError,
    OmniRouteService,
)

PRIMARY = "oc/mimo-v2.5-free"
FALLBACK = "openai-compatible-chat-38d59294-9537-4ebf-a7bd-c8853db07903/google/gemma-4-31b-it:free"
MESSAGES = [
    {"role": "user", "content": [
        {"type": "text", "text": "test"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}},
    ]},
]


def _settings(*, fallback: str = FALLBACK) -> Settings:
    return Settings(
        omniroute_base_url="http://test:9999/v1",
        omniroute_api_key="",
        omniroute_model="auto/coding:free",
        omniroute_vision_model=PRIMARY,
        omniroute_vision_fallback_model=fallback,
    )


_FAKE_REQUEST = httpx.Request("POST", "http://test:9999/v1/chat/completions")


def _make_response(status: int, **kwargs) -> httpx.Response:
    resp = httpx.Response(status, request=_FAKE_REQUEST, **kwargs)
    return resp


def _ok_response(model: str = "effective-model") -> httpx.Response:
    return _make_response(
        200,
        json={
            "choices": [{"message": {"content": '{"result":"ok"}'}}],
            "model": model,
        },
    )


def _rate_limit_response() -> httpx.Response:
    return _make_response(429, json={"error": "rate limit"})


def _server_error_response(code: int = 500) -> httpx.Response:
    return _make_response(code, json={"error": "server error"})


class FakeAsyncClient:
    """Simula httpx.AsyncClient com respostas sequenciais predefinidas."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self._calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, *, headers=None, json=None):
        self._calls.append({"url": url, "json": json})
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def models_sent(self) -> list[str]:
        return [c["json"]["model"] for c in self._calls]


def _run(client, svc):
    with patch("app.services.omniroute.httpx.AsyncClient", return_value=client):
        return asyncio.run(svc.complete_vision_json(MESSAGES, timeout_seconds=30))


def _run_raises(client, svc):
    with patch("app.services.omniroute.httpx.AsyncClient", return_value=client):
        with pytest.raises(OmniRouteError) as exc_info:
            asyncio.run(svc.complete_vision_json(MESSAGES, timeout_seconds=30))
        return exc_info.value


# ==========================================
# 1) PRIMARY OK — NO FALLBACK
# ==========================================

class TestPrimaryOk:
    def test_primary_works_no_fallback(self):
        client = FakeAsyncClient([_ok_response("mimo-v2.5-free")])
        result = _run(client, OmniRouteService(_settings()))

        assert result.content == '{"result":"ok"}'
        assert result.model == "mimo-v2.5-free"
        assert result.fallback_used is False
        assert result.fallback_reason is None
        assert client.call_count == 1
        assert client.models_sent == [PRIMARY]


# ==========================================
# 2) PRIMARY RATE LIMITED -> FALLBACK OK
# ==========================================

class TestRateLimitFallback:
    def test_primary_429_fallback_succeeds(self):
        client = FakeAsyncClient([
            _rate_limit_response(),
            _ok_response("gemma-4-31b-it:free"),
        ])
        result = _run(client, OmniRouteService(_settings()))

        assert result.content == '{"result":"ok"}'
        assert result.model == "gemma-4-31b-it:free"
        assert result.fallback_used is True
        assert result.fallback_reason == "RATE_LIMIT"
        assert client.call_count == 2
        assert client.models_sent == [PRIMARY, FALLBACK]


# ==========================================
# 3) PRIMARY TIMEOUT -> FALLBACK OK
# ==========================================

class TestTimeoutFallback:
    def test_primary_timeout_fallback_succeeds(self):
        client = FakeAsyncClient([
            httpx.ReadTimeout("timeout"),
            _ok_response("gemma-4-31b-it:free"),
        ])
        result = _run(client, OmniRouteService(_settings()))

        assert result.content == '{"result":"ok"}'
        assert result.fallback_used is True
        assert result.fallback_reason == "TIMEOUT"
        assert client.call_count == 2


# ==========================================
# 4) PRIMARY 500 -> FALLBACK OK
# ==========================================

class TestServerErrorFallback:
    def test_primary_502_fallback_succeeds(self):
        client = FakeAsyncClient([
            _server_error_response(502),
            _ok_response("gemma-4-31b-it:free"),
        ])
        result = _run(client, OmniRouteService(_settings()))

        assert result.fallback_used is True
        assert result.fallback_reason == "HTTP_502"
        assert client.models_sent == [PRIMARY, FALLBACK]


# ==========================================
# 5) PERMANENT ERROR -> NO FALLBACK
# ==========================================

class TestPermanentErrorNoFallback:
    def test_primary_400_raises_immediately(self):
        client = FakeAsyncClient([
            _make_response(400, json={"error": "bad request"}),
        ])
        exc = _run_raises(client, OmniRouteService(_settings()))

        assert exc.status_code == 502
        assert client.call_count == 1
        assert client.models_sent == [PRIMARY]

    def test_empty_content_raises_without_fallback(self):
        bad = _make_response(
            200,
            json={"choices": [{"message": {"content": ""}}]},
        )
        client = FakeAsyncClient([bad])
        with patch("app.services.omniroute.httpx.AsyncClient", return_value=client):
            with pytest.raises(OmniRouteError, match="inv"):
                asyncio.run(
                    OmniRouteService(_settings()).complete_vision_json(
                        MESSAGES, timeout_seconds=30
                    )
                )

        assert client.call_count == 1


# ==========================================
# 6) ALL MODELS FAIL
# ==========================================

class TestAllFail:
    def test_both_rate_limited_raises_503(self):
        client = FakeAsyncClient([
            _rate_limit_response(),
            _rate_limit_response(),
        ])
        exc = _run_raises(client, OmniRouteService(_settings()))

        assert exc.status_code == 503
        assert "RATE_LIMIT" in str(exc)
        assert client.call_count == 2

    def test_both_timeout_raises_503(self):
        client = FakeAsyncClient([
            httpx.ReadTimeout("t1"),
            httpx.ReadTimeout("t2"),
        ])
        exc = _run_raises(client, OmniRouteService(_settings()))

        assert exc.status_code == 503
        assert "TIMEOUT" in str(exc)


# ==========================================
# 7) NO FALLBACK CONFIGURED
# ==========================================

class TestNoFallbackConfigured:
    def test_no_fallback_only_primary_attempted(self):
        client = FakeAsyncClient([_rate_limit_response()])
        exc = _run_raises(client, OmniRouteService(_settings(fallback="")))

        assert exc.status_code == 503
        assert client.call_count == 1
        assert client.models_sent == [PRIMARY]


# ==========================================
# 8) EFFECTIVE MODEL RECORDED
# ==========================================

class TestModelProvenance:
    def test_effective_model_from_response(self):
        client = FakeAsyncClient([_ok_response("xiaomi/mimo-v2.5")])
        result = _run(client, OmniRouteService(_settings()))

        assert result.model == "xiaomi/mimo-v2.5"
        assert result.fallback_used is False

    def test_fallback_model_used_when_response_has_no_model(self):
        resp = _make_response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
        )
        client = FakeAsyncClient([_rate_limit_response(), resp])
        result = _run(client, OmniRouteService(_settings()))

        assert result.model == FALLBACK
        assert result.fallback_used is True


# ==========================================
# 9) COST GATE — ONLY FREE MODELS
# ==========================================

class TestCostGate:
    def test_primary_is_free(self):
        assert "free" in PRIMARY

    def test_fallback_is_free(self):
        assert "free" in FALLBACK

    def test_default_config_models_are_free(self):
        s = Settings()
        assert "free" in s.omniroute_vision_model
        assert "free" in s.omniroute_vision_fallback_model
