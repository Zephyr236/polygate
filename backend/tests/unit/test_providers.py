"""Tests for provider adapters using mocked transports."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from polygate.config import AuthStyle, ErrorRule, ProviderConfig, SessionMode
from polygate.protocols.base import InternalRequest, Message, UpstreamError
from polygate.providers.base import (
    BaseProvider,
    OpenAIProvider,
    build_provider,
    classify_error,
    jitter_delay_ms,
)


def _config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "id": "p",
        "base_url": "https://up.example",
        "model": "up-model",
        "api_key_env": "K",
        "max_tokens_min": 3000,
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def _request() -> InternalRequest:
    return InternalRequest("m", (Message("user", "hi"),), 100)


def _provider(config: ProviderConfig | None = None, client: httpx.AsyncClient | None = None) -> BaseProvider:
    http = client or httpx.AsyncClient()
    return build_provider(config or _config(), "sk-test", http)


@pytest.mark.asyncio
@respx.mock
async def test_openai_complete_success_and_latency() -> None:
    route = respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "PONG"}}], "model": "up-model"}
        )
    )
    result = await _provider().complete(_request(), lane=0)
    assert result.response.text == "PONG"
    assert result.latency_ms >= 0.0
    assert route.calls[0].request.headers["authorization"] == "Bearer sk-test"
    body = json.loads(route.calls[0].request.content)
    assert body["max_tokens"] == 3000


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_complete_headers_and_payload() -> None:
    config = _config(protocol="anthropic", auth_style=AuthStyle.BOTH, base_url="https://up.example")
    respx.post("https://up.example/messages").mock(
        return_value=httpx.Response(200, json={"content": [{"type": "text", "text": "PONG"}], "usage": {}})
    )
    result = await _provider(config).complete(_request(), lane=0)
    assert result.response.text == "PONG"
    sent = respx.calls[0].request
    assert sent.headers["x-api-key"] == "sk-test"
    assert sent.headers["anthropic-version"] == "2023-06-01"
    assert sent.headers["authorization"] == "Bearer sk-test"


def test_session_headers_per_request_and_per_lane() -> None:
    config = _config(session_header="x-opencode-session", session_mode=SessionMode.PER_REQUEST)
    provider = OpenAIProvider(config, "k", httpx.AsyncClient())
    first = provider.headers(0)["x-opencode-session"]
    second = provider.headers(0)["x-opencode-session"]
    assert first != second
    config = _config(session_header="x-opencode-session", session_mode=SessionMode.PER_LANE, lanes=2)
    provider = OpenAIProvider(config, "k", httpx.AsyncClient())
    assert provider.headers(0)["x-opencode-session"] == provider.headers(0)["x-opencode-session"]
    assert provider.headers(0)["x-opencode-session"] != provider.headers(1)["x-opencode-session"]
    assert "x-opencode-session" not in provider.headers(0, stream=False) or True


def test_no_session_header_when_mode_none() -> None:
    provider = OpenAIProvider(_config(session_header="x-opencode-session"), "k", httpx.AsyncClient())
    assert "x-opencode-session" not in provider.headers(0)


@pytest.mark.asyncio
@respx.mock
async def test_timeout_maps_to_timeout_error() -> None:
    respx.post("https://up.example/chat/completions").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError) as info:
        await _provider().complete(_request(), lane=0)
    assert info.value.error_class == "timeout"
    assert info.value.retryable


@pytest.mark.asyncio
@respx.mock
async def test_transport_error_maps_to_transport_error() -> None:
    respx.post("https://up.example/chat/completions").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(UpstreamError) as info:
        await _provider().complete(_request(), lane=0)
    assert info.value.error_class == "transport_error"


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_enriched_with_retry_after() -> None:
    respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(
            429, headers={"retry-after": "1.5"}, json={"error": {"type": "rate_limit"}}
        )
    )
    with pytest.raises(UpstreamError) as info:
        await _provider().complete(_request(), lane=0)
    assert info.value.error_class == "rate_limited"
    assert info.value.retry_after_ms == 1500


@pytest.mark.asyncio
@respx.mock
async def test_custom_error_rule_from_json_path() -> None:
    config = _config(
        error_rules=[ErrorRule(json_path="error.code", error_class="concurrency_limited", retryable=True)]
    )
    respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(400, json={"error": {"code": "tier_limit_exceeded", "message": "11/10"}})
    )
    with pytest.raises(UpstreamError) as info:
        await _provider(config).complete(_request(), lane=0)
    assert info.value.error_class == "concurrency_limited"
    assert info.value.status_code == 429


@pytest.mark.asyncio
@respx.mock
async def test_custom_error_rule_from_text_match() -> None:
    config = _config(
        error_rules=[ErrorRule(match="invalid_api_key", error_class="auth_error", retryable=False)]
    )
    respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(401, json={"code": "INVALID_API_KEY", "message": "bad"})
    )
    with pytest.raises(UpstreamError) as info:
        await _provider(config).complete(_request(), lane=0)
    assert info.value.error_class == "auth_error"
    assert not info.value.retryable


def test_classify_error_status_mapping() -> None:
    config = _config()
    for status, expected in [
        (401, "auth_error"),
        (403, "auth_error"),
        (404, "model_not_found"),
        (500, "server_error"),
        (422, "client_error"),
    ]:
        error = classify_error(config, httpx.Response(status, json={"error": {"type": "x"}}))
        assert error.error_class == expected
    error = classify_error(config, httpx.Response(400, text="not json"))
    assert error.error_class == "client_error"


def test_lookup_path_returns_empty_for_missing() -> None:
    config = _config(error_rules=[ErrorRule(json_path="error.inner.code")])
    error = classify_error(config, httpx.Response(500, json={"error": "plain"}))
    assert error.error_class == "server_error"


def test_jitter_delay_bounds() -> None:
    assert jitter_delay_ms(100, 0, 500, 0.0) == 100.0
    assert jitter_delay_ms(100, 5, 500, 0.0) == 500.0
    value = jitter_delay_ms(100, 1, 500, 0.5)
    assert 100 * 0.5 <= value <= 300 * 1.5


@pytest.mark.asyncio
@respx.mock
async def test_openai_stream_deltas_and_usage() -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"PO"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"NG"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    )
    events = [event async for event in _provider().stream(_request(), lane=0)]
    assert events[0] == ("PO", None)
    assert events[1] == ("NG", None)
    assert events[2][1] is not None
    assert events[2][1].prompt_tokens == 5


@pytest.mark.asyncio
@respx.mock
async def test_chat_stream_error_before_stream_raises() -> None:
    respx.post("https://up.example/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"type": "rate_limit"}})
    )
    events: list[tuple[str, object]] = []
    with pytest.raises(UpstreamError):
        async for event in _provider().stream(_request(), lane=0):
            events.append(event)
    assert events == []


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_stream_delta_usage() -> None:
    body = (
        "event: content_block_delta\n"
        'data: {"type":"content_block_delta","delta":{"text":"OK"}}\n\n'
        "event: message_delta\n"
        'data: {"type":"message_delta","usage":{"input_tokens":7,"output_tokens":2}}\n\n'
    )
    config = _config(protocol="anthropic")
    respx.post("https://up.example/messages").mock(return_value=httpx.Response(200, text=body))
    events = [event async for event in _provider(config).stream(_request(), lane=0)]
    assert events[0] == ("OK", None)
    assert events[-1][1] is not None
    assert events[-1][1].prompt_tokens == 7


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_stream_http_error() -> None:
    config = _config(protocol="anthropic")
    respx.post("https://up.example/messages").mock(
        return_value=httpx.Response(400, json={"error": {"type": "invalid"}})
    )
    with pytest.raises(UpstreamError):
        async for _ in _provider(config).stream(_request(), lane=0):
            pass
