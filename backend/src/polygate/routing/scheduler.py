"""Provider selection, lane reservation, retries and failover for both request modes."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from polygate.config import ClientPolicy, ProviderConfig, RoutingConfig
from polygate.protocols.base import (
    AllProvidersFailedError,
    InternalRequest,
    InternalResponse,
    UpstreamError,
    Usage,
)
from polygate.providers.base import BaseProvider, UpstreamResult, jitter_delay_ms
from polygate.routing.scorer import rank_candidates
from polygate.routing.state import Clock, HealthRegistry, ProviderState

Sleep = Callable[[float], Awaitable[None]]


ProviderFactory = Callable[[ProviderConfig, str], BaseProvider]


@dataclass
class Attempt:
    """Recorded outcome of one provider attempt."""

    provider_id: str
    error_class: str | None = None
    retryable: bool = False
    detail: str = ""


@dataclass
class RouteResult:
    """Successful routing outcome with the attempt trail."""

    result: UpstreamResult
    attempts: list[Attempt]


@dataclass
class Selection:
    """A reserved provider lane ready for one call."""

    config: ProviderConfig
    state: ProviderState
    lane: int


@dataclass
class StreamBuffer:
    """FIFO buffer of stream deltas for a single attempt."""

    _items: list[tuple[str, Usage | None, str]] = field(default_factory=list)
    failed: bool = False

    def push(self, item: tuple[str, Usage | None, str]) -> None:
        """Append one delta."""
        self._items.append(item)

    def pop(self) -> tuple[str, Usage | None, str]:
        """Remove and return the oldest delta."""
        return self._items.pop(0)

    def has_items(self) -> bool:
        """Report whether buffered deltas remain."""
        return bool(self._items)


def utc_hour_weekday(now: datetime | None = None) -> tuple[int, int]:
    """Return the current UTC hour and ISO weekday."""
    moment = now or datetime.now(timezone.utc)
    return moment.hour, moment.isoweekday()


def tagged_response(response: InternalResponse, provider_id: str) -> InternalResponse:
    """Return a response copy carrying the serving provider id."""
    return InternalResponse(
        text=response.text,
        thinking=response.thinking,
        model=response.model,
        provider_id=provider_id,
        usage=response.usage,
        finish_reason=response.finish_reason,
    )


class Scheduler:
    """Routes requests across providers with retries, lane gating and failover."""

    # Construction wiring: providers, policy, health registry, adapter factory, clocks.

    def __init__(
        self,
        providers: list[ProviderConfig],
        routing: RoutingConfig,
        health: HealthRegistry,
        factory: ProviderFactory,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        self.providers = providers
        self.routing = routing
        self.health = health
        self._factory = factory
        self._adapters: dict[str, BaseProvider] = {}
        self._sleep = sleep
        self._clock = clock

    def set_adapters(self, adapters: dict[str, BaseProvider]) -> None:
        """Install prebuilt adapters."""
        self._adapters = adapters

    def prune_adapters(self, keep: set[str]) -> None:
        """Drop cached adapters for providers no longer in the pool."""
        for provider_id in list(self._adapters):
            if provider_id not in keep:
                del self._adapters[provider_id]

    def _adapter(self, config: ProviderConfig, keys: dict[str, str]) -> BaseProvider:
        """Return the cached adapter, building it on first use."""
        adapter = self._adapters.get(config.id)
        if adapter is None:
            adapter = self._factory(config, keys.get(config.api_key_env, ""))
            self._adapters[config.id] = adapter
        return adapter

    def _candidates(
        self, excluded: set[str], policy: ClientPolicy | None
    ) -> list[tuple[ProviderConfig, ProviderState]]:
        """Filter, score and order eligible providers outside the exclusion set."""
        hour, weekday = utc_hour_weekday()
        allowed = [
            config for config in self.providers if policy is None or policy.allows(config.id)
        ]
        routing = self.routing
        if policy is not None and policy.weights is not None:
            routing = self.routing.model_copy(update={"weights": policy.weights})
        ranked = rank_candidates(allowed, self.health.states(), routing, hour, weekday, excluded)
        configs = {config.id: config for config in allowed}
        pairs: list[tuple[ProviderConfig, ProviderState]] = []
        for score in ranked:
            state = self.health.get(score.provider_id)
            if state is not None and self.health.available(score.provider_id, self._clock()):
                pairs.append((configs[score.provider_id], state))
        return pairs

    def _select(self, excluded: set[str], policy: ClientPolicy | None) -> Selection | None:
        """Reserve the best-scoring provider lane outside the exclusion set."""
        for config, state in self._candidates(excluded, policy):
            lane = state.acquire()
            if lane is not None:
                return Selection(config, state, lane)
        return None

    async def complete(
        self,
        request: InternalRequest,
        keys: dict[str, str],
        policy: ClientPolicy | None = None,
    ) -> RouteResult:
        """Route one non-streaming request, switching providers on failure."""
        attempts: list[Attempt] = []
        excluded: set[str] = set()
        for _ in range(self.routing.max_switches + 1):
            selection = self._select(excluded, policy)
            if selection is None:
                break
            outcome = await self._run(selection, request, keys, attempts)
            if outcome is not None:
                return RouteResult(outcome, attempts)
            excluded.add(selection.config.id)
        raise AllProvidersFailedError([attempt.__dict__ for attempt in attempts])

    async def _run(
        self, selection: Selection, request: InternalRequest, keys: dict[str, str], attempts: list[Attempt]
    ) -> UpstreamResult | None:
        adapter = self._adapter(selection.config, keys)
        try:
            return await self._retry(adapter, request, selection.config, selection.lane, attempts)
        finally:
            selection.state.release(selection.lane)

    async def _retry(
        self,
        adapter: BaseProvider,
        request: InternalRequest,
        config: ProviderConfig,
        lane: int,
        attempts: list[Attempt],
    ) -> UpstreamResult | None:
        for retry in range(config.retry.attempts):
            started = time.perf_counter()
            try:
                result = await adapter.complete(request, lane)
            except UpstreamError as error:
                attempts.append(Attempt(config.id, error.error_class, error.retryable, error.message))
                self.health.record_failure(config.id, error.error_class)
                if not error.retryable or retry + 1 >= config.retry.attempts:
                    return None
                await self._sleep(self._backoff(config, retry))
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000
            self.health.record_success(config.id, elapsed_ms, result.response.usage.cache_hit)
            return result
        return None

    def _backoff(self, config: ProviderConfig, retry: int) -> float:
        """Compute the retry delay in seconds."""
        delay_ms = jitter_delay_ms(
            config.retry.base_delay_ms, retry, config.retry.max_delay_ms, config.retry.jitter
        )
        return delay_ms / 1000.0

    async def stream(
        self,
        request: InternalRequest,
        keys: dict[str, str],
        policy: ClientPolicy | None = None,
    ) -> AsyncIterator[tuple[str, Usage | None, str]]:
        """Route one streaming request, yielding deltas tagged with their provider."""
        attempts: list[Attempt] = []
        excluded: set[str] = set()
        async for buffer in self._stream_attempts(request, keys, attempts, excluded, policy):
            while buffer.has_items():
                yield buffer.pop()
            if not buffer.failed:
                return
        raise AllProvidersFailedError([attempt.__dict__ for attempt in attempts])

    async def _stream_attempts(
        self,
        request: InternalRequest,
        keys: dict[str, str],
        attempts: list[Attempt],
        excluded: set[str],
        policy: ClientPolicy | None = None,
    ) -> AsyncIterator[StreamBuffer]:
        for _ in range(self.routing.max_switches + 1):
            selection = self._select(excluded, policy)
            if selection is None:
                return
            buffer = await self._fill(selection, request, keys, attempts)
            excluded.add(selection.config.id)
            yield buffer
            if not buffer.failed:
                return

    async def _fill(
        self,
        selection: Selection,
        request: InternalRequest,
        keys: dict[str, str],
        attempts: list[Attempt],
    ) -> StreamBuffer:
        """Fill a buffer with deltas from one reserved lane."""
        buffer = StreamBuffer()
        await self._stream_lane(self._adapter(selection.config, keys), request, selection, attempts, buffer)
        return buffer

    async def _stream_lane(
        self,
        adapter: BaseProvider,
        request: InternalRequest,
        selection: Selection,
        attempts: list[Attempt],
        buffer: StreamBuffer,
    ) -> bool:
        emitted = False
        completed = False
        try:
            async for text, usage in adapter.stream(request, selection.lane):
                emitted = True
                buffer.push((text, usage, selection.config.id))
        except UpstreamError as error:
            attempts.append(Attempt(selection.config.id, error.error_class, error.retryable, error.message))
            self.health.record_failure(selection.config.id, error.error_class)
            if emitted:
                raise
        else:
            completed = True
        finally:
            selection.state.release(selection.lane)
        if completed:
            self.health.record_success(selection.config.id, 0.0, False)
        buffer.failed = not completed
        return completed
