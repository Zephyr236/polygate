"""Provider adapters that talk to OpenAI-compatible and Anthropic-compatible upstreams."""

from __future__ import annotations

import json
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from polygate.config import AuthStyle, ErrorRule, Protocol, ProviderConfig, SessionMode
from polygate.protocols import anthropic, openai
from polygate.protocols.base import InternalRequest, InternalResponse, UpstreamError, Usage
from polygate.protocols.sse import iter_anthropic_deltas, iter_openai_deltas


@dataclass(frozen=True)
class UpstreamResult:
    """One successful upstream call with its timing."""

    response: InternalResponse
    latency_ms: float


def _error_body_text(response: httpx.Response) -> tuple[str, dict[str, Any]]:
    """Capture a bounded error body text together with its JSON payload."""
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:500], {}
    return json.dumps(payload, ensure_ascii=False)[:500], payload


def _lookup_path(payload: dict[str, Any], path: str) -> str:
    """Read a dotted JSON path, returning an empty string when absent."""
    node: Any = payload
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return ""
        node = node[part]
    return str(node)


ERROR_STATUS = {
    "rate_limited": 429,
    "concurrency_limited": 429,
    "auth_error": 401,
    "model_not_found": 404,
    "client_error": 400,
    "timeout": 504,
    "transport_error": 503,
}


def _error_type(payload: dict[str, Any]) -> str:
    """Return the upstream error type when it is a string field."""
    error = payload.get("error")
    return str(error.get("type", "")) if isinstance(error, dict) else ""


def _rule_match(rule: ErrorRule, text: str, payload: dict[str, Any]) -> bool:
    """Report whether an error rule matches the payload or text."""
    if rule.json_path is not None and _lookup_path(payload, rule.json_path):
        return True
    return rule.match is not None and rule.match.lower() in text.lower()


def classify_by_rule(
    config: ProviderConfig, text: str, payload: dict[str, Any], status: int
) -> UpstreamError | None:
    """Map the first matching configured error rule onto a normalized error."""
    for rule in config.error_rules:
        if _rule_match(rule, text, payload):
            return UpstreamError(
                text, rule.error_class, _status_for(rule.error_class, status), rule.retryable
            )
    return None


def status_to_class(status: int, error_type: str) -> str:
    """Map a bare HTTP status and error type onto a default error class."""
    if status == 429 or "rate" in error_type:
        return "rate_limited"
    if status in {401, 403}:
        return "auth_error"
    if status == 404:
        return "model_not_found"
    if status >= 500:
        return "server_error"
    return "client_error"


def classify_error(config: ProviderConfig, response: httpx.Response) -> UpstreamError:
    """Map an upstream error response onto a normalized error class."""
    text, payload = _error_body_text(response)
    ruled = classify_by_rule(config, text, payload, response.status_code)
    if ruled is not None:
        return ruled
    error_class = status_to_class(response.status_code, _error_type(payload))
    retryable = error_class in {"rate_limited", "server_error"}
    status = 429 if error_class == "rate_limited" else _status_for(error_class, response.status_code)
    return UpstreamError(text, error_class, status, retryable, _retry_after_ms(response))


def _status_for(error_class: str, upstream_status: int) -> int:
    """Map a normalized error class onto the client-facing status."""
    known = ERROR_STATUS.get(error_class)
    if known is not None:
        return known
    if upstream_status in {400, 401, 403, 404, 429}:
        return upstream_status
    return 502


def _retry_after_ms(response: httpx.Response) -> int | None:
    """Parse the retry-after header into milliseconds."""
    raw = response.headers.get("retry-after", "")
    if not raw:
        return None
    try:
        return int(float(raw) * 1000)
    except ValueError:
        return None


class SessionHeaders:
    """Mint session identifiers for lanes and expose them as headers."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._lane_sessions = [uuid.uuid4().hex for _ in range(config.lanes)]

    def session_for(self, lane: int) -> str:
        """Return the session id for a lane, minting one per request when configured."""
        if self._config.session_mode is SessionMode.PER_LANE:
            return self._lane_sessions[lane]
        return uuid.uuid4().hex

    def headers(self, lane: int) -> dict[str, str]:
        """Build the session header for the lane when one is configured."""
        if not self._config.session_header or self._config.session_mode is SessionMode.NONE:
            return {}
        return {self._config.session_header: self.session_for(lane)}


class AuthHeaders:
    """Build credential headers for the configured auth style."""

    def __init__(self, config: ProviderConfig, api_key: str) -> None:
        self._config = config
        self._api_key = api_key

    def headers(self) -> dict[str, str]:
        """Build credential headers for the configured auth style."""
        headers: dict[str, str] = {}
        if self._config.auth_style is not AuthStyle.X_API_KEY:
            headers["authorization"] = f"Bearer {self._api_key}"
        if self._config.auth_style is not AuthStyle.BEARER:
            headers["x-api-key"] = self._api_key
            headers["anthropic-version"] = "2023-06-01"
        return headers


class BaseProvider(ABC):
    """Shared authentication, session and error handling for upstream adapters."""

    def __init__(self, config: ProviderConfig, api_key: str, client: httpx.AsyncClient) -> None:
        self.config = config
        self.api_key = api_key
        self.client = client
        self._sessions = SessionHeaders(config)
        self._auth = AuthHeaders(config, api_key)

    def headers(self, lane: int, stream: bool = False) -> dict[str, str]:
        """Build authentication and session headers for one call."""
        headers = {"content-type": "application/json", **self._auth.headers(), **self._sessions.headers(lane)}
        if stream:
            headers["accept"] = "text/event-stream"
        return headers

    @abstractmethod
    async def complete(self, request: InternalRequest, lane: int) -> UpstreamResult:
        """Perform one non-streaming upstream call."""

    @abstractmethod
    def stream(self, request: InternalRequest, lane: int) -> AsyncIterator[tuple[str, Usage | None]]:
        """Yield text deltas and final usage from a streaming upstream call."""

    def _url(self, suffix: str) -> str:
        """Join the provider base URL with a protocol suffix."""
        return f"{self.config.base_url.rstrip('/')}{suffix}"

    async def _post(self, suffix: str, payload: dict[str, Any], lane: int) -> httpx.Response:
        """POST a JSON body and normalize transport failures."""
        try:
            response = await self.client.post(
                self._url(suffix),
                json=payload,
                headers=self.headers(lane),
                timeout=httpx.Timeout(
                    self.config.timeouts.total_seconds, connect=self.config.timeouts.connect_seconds
                ),
            )
        except httpx.TimeoutException as error:
            raise UpstreamError(f"timeout: {error}", "timeout", 504, True) from error
        except httpx.HTTPError as error:
            raise UpstreamError(f"transport: {error}", "transport_error", 503, True) from error
        if response.status_code >= 400:
            raise classify_error(self.config, response)
        return response

    async def _post_stream(self, suffix: str, payload: dict[str, Any], lane: int) -> httpx.Response:
        """Start a streaming POST and return the live response."""
        request = self.client.build_request(
            "POST",
            self._url(suffix),
            json=payload,
            headers=self.headers(lane, stream=True),
            timeout=httpx.Timeout(
                self.config.timeouts.total_seconds, connect=self.config.timeouts.connect_seconds
            ),
        )
        try:
            return await self.client.send(request, stream=True)
        except httpx.TimeoutException as error:
            raise UpstreamError(f"timeout: {error}", "timeout", 504, True) from error
        except httpx.HTTPError as error:
            raise UpstreamError(f"transport: {error}", "transport_error", 503, True) from error


class OpenAIProvider(BaseProvider):
    """Adapter for OpenAI chat-completions upstreams."""

    async def complete(self, request: InternalRequest, lane: int) -> UpstreamResult:
        """Perform one non-streaming completion."""
        payload = openai.to_upstream_payload(request, self.config.model, self.config.max_tokens_min)
        started = time.perf_counter()
        response = await self._post("/chat/completions", payload, lane)
        elapsed = (time.perf_counter() - started) * 1000
        return UpstreamResult(openai.parse_response(response.json(), self.config.id), elapsed)

    async def stream(self, request: InternalRequest, lane: int) -> AsyncIterator[tuple[str, Usage | None]]:
        """Yield text deltas and final usage from a streaming completion."""
        payload = openai.to_upstream_payload(request, self.config.model, self.config.max_tokens_min)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        response = await self._post_stream("/chat/completions", payload, lane)
        if response.status_code >= 400:
            await response.aread()
            await response.aclose()
            raise classify_error(self.config, response)
        try:
            async for line in response.aiter_lines():
                for text, usage_payload in iter_openai_deltas([line]):
                    usage = openai.parse_usage({"usage": usage_payload}) if usage_payload else None
                    yield text, usage if usage and usage.prompt_tokens else None
        finally:
            await response.aclose()


class AnthropicProvider(BaseProvider):
    """Adapter for Anthropic messages upstreams."""

    async def complete(self, request: InternalRequest, lane: int) -> UpstreamResult:
        """Perform one non-streaming message call."""
        payload = anthropic.to_upstream_payload(request, self.config.model, self.config.max_tokens_min)
        started = time.perf_counter()
        response = await self._post("/messages", payload, lane)
        elapsed = (time.perf_counter() - started) * 1000
        return UpstreamResult(anthropic.parse_response(response.json(), self.config.id), elapsed)

    async def stream(self, request: InternalRequest, lane: int) -> AsyncIterator[tuple[str, Usage | None]]:
        """Yield text deltas and final usage from a streaming message call."""
        payload = anthropic.to_upstream_payload(request, self.config.model, self.config.max_tokens_min)
        payload["stream"] = True
        response = await self._post_stream("/messages", payload, lane)
        if response.status_code >= 400:
            await response.aread()
            await response.aclose()
            raise classify_error(self.config, response)
        try:
            async for line in response.aiter_lines():
                for text, usage_payload in iter_anthropic_deltas([line]):
                    usage = anthropic.parse_usage({"usage": usage_payload}) if usage_payload else None
                    yield text, usage if usage and usage.prompt_tokens else None
        finally:
            await response.aclose()


def build_provider(config: ProviderConfig, api_key: str, client: httpx.AsyncClient) -> BaseProvider:
    """Instantiate the adapter matching the provider protocol."""
    if config.protocol is Protocol.ANTHROPIC:
        return AnthropicProvider(config, api_key, client)
    return OpenAIProvider(config, api_key, client)


def jitter_delay_ms(base_ms: int, attempt: int, max_ms: int, jitter: float) -> float:
    """Compute exponential backoff with multiplicative jitter."""
    delay = min(base_ms * (2**attempt), max_ms)
    spread = delay * jitter
    # Retry jitter is not a security primitive, so a pseudo-random source is acceptable.
    return float(delay + random.uniform(-spread, spread) if spread else delay)
