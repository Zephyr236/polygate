"""Tests for scheduler selection, retries, failover and streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from polygate.config import ProviderConfig, RoutingConfig
from polygate.protocols.base import (
    AllProvidersFailedError,
    InternalRequest,
    InternalResponse,
    Message,
    UpstreamError,
    Usage,
)
from polygate.providers.base import BaseProvider, UpstreamResult
from polygate.routing.scheduler import Scheduler, StreamBuffer, tagged_response, utc_hour_weekday
from polygate.routing.state import HealthRegistry


class ScriptedProvider(BaseProvider):
    """Provider stub returning scripted outcomes per call."""

    def __init__(self, config: ProviderConfig, outcome: str = "ok", fail_times: int = 0) -> None:
        super().__init__(config, "k", __import__("httpx").AsyncClient())
        self.outcome = outcome
        self.fail_times = fail_times
        self.calls = 0

    async def complete(self, request: InternalRequest, lane: int) -> UpstreamResult:
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise UpstreamError("boom", self.outcome, 502, True)
        if self.outcome != "ok":
            raise UpstreamError("boom", self.outcome, 502, self.outcome in {"rate_limited", "timeout"})
        return UpstreamResult(InternalResponse("PONG", "", "m", self.config.id, Usage(10, 2, 0, 0)), 5.0)

    async def stream(self, request: InternalRequest, lane: int) -> AsyncIterator[tuple[str, Usage | None]]:
        if self.outcome != "ok":
            raise UpstreamError("boom", self.outcome, 502, True)
        yield "PO", None
        yield "NG", Usage(3, 1)


def _config(provider_id: str, **overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "id": provider_id,
        "base_url": "https://x",
        "model": "m",
        "api_key_env": "K",
        "retry": {"attempts": 1, "base_delay_ms": 10},
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def _request() -> InternalRequest:
    return InternalRequest("m", (Message("user", "hi"),), 100, stream=True)


def _scheduler(
    configs: list[ProviderConfig],
    adapters: dict[str, BaseProvider],
    windows: list[float] | None = None,
    **routing: object,
) -> Scheduler:
    policy = RoutingConfig.model_validate(routing)
    health = HealthRegistry(
        configs,
        failure_threshold=policy.failure_threshold,
        cooldown_base_ms=1000,
        cooldown_max_ms=10_000,
        half_open_probes=1,
        success_alpha=0.5,
        latency_alpha=0.5,
    )
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    scheduler = Scheduler(
        configs,
        policy,
        health,
        factory=lambda config, key: adapters[config.id],
        sleep=fake_sleep,
    )
    scheduler.set_adapters(adapters)
    scheduler.delays = delays  # type: ignore[attr-defined]
    return scheduler


@pytest.mark.asyncio
async def test_complete_routes_to_first_candidate() -> None:
    configs = [_config("a")]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0])})
    result = await scheduler.complete(_request(), {"K": "k"})
    assert result.result.response.text == "PONG"
    assert result.result.response.provider_id == "a"
    assert result.attempts == []


@pytest.mark.asyncio
async def test_complete_fails_over_to_next_provider() -> None:
    configs = [_config("a", priority=0), _config("b", priority=1)]
    scheduler = _scheduler(
        configs,
        {"a": ScriptedProvider(configs[0], outcome="server_error"), "b": ScriptedProvider(configs[1])},
    )
    result = await scheduler.complete(_request(), {})
    assert result.result.response.provider_id == "b"
    assert result.attempts[0].provider_id == "a"
    assert result.attempts[0].error_class == "server_error"


@pytest.mark.asyncio
async def test_complete_raises_when_all_fail() -> None:
    configs = [_config("a")]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0], outcome="auth_error")})
    with pytest.raises(AllProvidersFailedError) as info:
        await scheduler.complete(_request(), {})
    assert len(info.value.attempts) == 1


@pytest.mark.asyncio
async def test_complete_respects_saturation_and_switch_budget() -> None:
    configs = [_config("a"), _config("b")]
    scheduler = _scheduler(
        configs, {"a": ScriptedProvider(configs[0]), "b": ScriptedProvider(configs[1])}, max_switches=1
    )
    for _ in range(8):
        assert scheduler.health.get("a").acquire() is not None  # type: ignore[union-attr]
    result = await scheduler.complete(_request(), {})
    assert result.result.response.provider_id == "b"


@pytest.mark.asyncio
async def test_complete_no_candidates_when_all_saturated() -> None:
    configs = [_config("a", max_concurrency=1)]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0])})
    assert scheduler.health.get("a").acquire() is not None  # type: ignore[union-attr]
    with pytest.raises(AllProvidersFailedError):
        await scheduler.complete(_request(), {})


@pytest.mark.asyncio
async def test_retry_on_transient_then_success() -> None:
    configs = [_config("a", retry={"attempts": 3, "base_delay_ms": 20, "max_delay_ms": 100, "jitter": 0.0})]
    provider = ScriptedProvider(configs[0], fail_times=2)
    scheduler = _scheduler(configs, {"a": provider})
    result = await scheduler.complete(_request(), {})
    assert result.result.response.provider_id == "a"
    assert provider.calls == 3
    assert len(scheduler.delays) == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_non_retryable_error_skips_retries() -> None:
    configs = [_config("a", retry={"attempts": 3, "base_delay_ms": 20})]
    provider = ScriptedProvider(configs[0], outcome="auth_error")
    scheduler = _scheduler(configs, {"a": provider})
    with pytest.raises(AllProvidersFailedError):
        await scheduler.complete(_request(), {})
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_stream_yields_deltas_and_usage() -> None:
    configs = [_config("a")]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0])})
    events = [event async for event in scheduler.stream(_request(), {})]
    assert events[0][0] == "PO"
    assert events[1][1] is not None
    assert events[1][1].prompt_tokens == 3


@pytest.mark.asyncio
async def test_stream_fails_over_before_first_delta() -> None:
    configs = [_config("a", priority=0), _config("b", priority=1)]
    scheduler = _scheduler(
        configs,
        {"a": ScriptedProvider(configs[0], outcome="server_error"), "b": ScriptedProvider(configs[1])},
    )
    events = [event async for event in scheduler.stream(_request(), {})]
    assert events[0][2] == "b"


@pytest.mark.asyncio
async def test_stream_all_fail_raises() -> None:
    configs = [_config("a")]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0], outcome="timeout")})
    with pytest.raises(AllProvidersFailedError):
        async for _ in scheduler.stream(_request(), {}):
            pass


def test_utc_hour_weekday_defaults_to_now() -> None:
    hour, weekday = utc_hour_weekday()
    assert 0 <= hour <= 23
    assert 1 <= weekday <= 7


def test_stream_buffer_fifo() -> None:
    buffer = StreamBuffer()
    assert not buffer.has_items()
    buffer.push(("a", None, "p"))
    buffer.push(("b", None, "p"))
    assert buffer.pop()[0] == "a"
    assert buffer.pop()[0] == "b"


def test_prune_adapters_drops_unknown_ids() -> None:
    configs = [_config("a")]
    scheduler = _scheduler(configs, {"a": ScriptedProvider(configs[0]), "gone": ScriptedProvider(configs[0])})
    scheduler.prune_adapters({"a"})
    assert set(scheduler._adapters) == {"a"}


@pytest.mark.asyncio
async def test_complete_uses_factory_when_adapter_missing() -> None:
    created: list[str] = []

    def factory(config: ProviderConfig, key: str) -> BaseProvider:
        created.append(key)
        return ScriptedProvider(config)

    configs = [_config("a")]
    policy = RoutingConfig()
    health = HealthRegistry(configs, 3, 1000, 10_000, 1, 0.5, 0.5)
    scheduler = Scheduler(configs, policy, health, factory)
    result = await scheduler.complete(_request(), {"K": "secret"})
    assert result.result.response.provider_id == "a"
    assert created == ["secret"]


def test_tagged_response_preserves_fields() -> None:
    original = InternalResponse("T", "W", "model-z", "old", Usage(4, 2, 1, 3), "length")
    tagged = tagged_response(original, "new")
    assert tagged == InternalResponse("T", "W", "model-z", "new", Usage(4, 2, 1, 3), "length")
    assert tagged.provider_id == "new"
    assert tagged.finish_reason == "length"


def test_utc_hour_weekday_uses_supplied_time() -> None:
    assert utc_hour_weekday(datetime(2026, 11, 22, 5, 30, tzinfo=timezone.utc)) == (5, 7)
