"""Provider health state, sliding statistics and circuit breaker transitions."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from polygate.config import ProviderConfig


class CircuitState(str, Enum):
    """Lifecycle state of a provider circuit."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderStats:
    """Mutable statistics for a single provider lane group."""

    success_rate: float = 1.0
    latency_ms: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    cache_hit_rate: float = 0.0
    last_error: str | None = None

    def record_success(self, latency_ms: float, alpha: float, cache_hit: bool, latency_alpha: float) -> None:
        """Fold one successful call into the moving averages."""
        self.total_calls += 1
        self.consecutive_failures = 0
        self.success_rate = alpha * 1.0 + (1 - alpha) * self.success_rate
        self.latency_ms = latency_alpha * latency_ms + (1 - latency_alpha) * self.latency_ms
        hit = 1.0 if cache_hit else 0.0
        self.cache_hit_rate = alpha * hit + (1 - alpha) * self.cache_hit_rate

    def record_failure(self, error: str, alpha: float) -> None:
        """Fold one failed call into the moving averages."""
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_error = error
        self.success_rate = alpha * 0.0 + (1 - alpha) * self.success_rate


@dataclass
class ProviderState:
    """Health snapshot for a provider including breaker and cooldown bookkeeping."""

    config: ProviderConfig
    stats: ProviderStats = field(default_factory=ProviderStats)
    state: CircuitState = CircuitState.CLOSED
    opened_until: float = 0.0
    probes_left: int = 0
    inflight: int = 0
    lane_inflight: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.lane_inflight:
            self.lane_inflight = [0 for _ in range(self.config.lanes)]

    def capacity(self) -> int:
        """Return the total number of concurrency slots across lanes."""
        return self.config.max_concurrency * self.config.lanes

    def inflight_total(self) -> int:
        """Return the current number of occupied slots."""
        return self.inflight

    def acquire(self) -> int | None:
        """Reserve one slot and return the lane index, or None when saturated."""
        if self.inflight >= self.capacity():
            return None
        for index, used in enumerate(self.lane_inflight):
            if used < self.config.max_concurrency:
                self.lane_inflight[index] = used + 1
                self.inflight += 1
                return index
        return None

    def release(self, lane: int) -> None:
        """Release one slot on a lane."""
        if self.lane_inflight[lane] > 0:
            self.lane_inflight[lane] -= 1
        if self.inflight > 0:
            self.inflight -= 1


Clock = Callable[[], float]


class HealthRegistry:
    """Registry of provider health cells with breaker transitions."""

    def __init__(
        self,
        configs: list[ProviderConfig],
        failure_threshold: int,
        cooldown_base_ms: int,
        cooldown_max_ms: int,
        half_open_probes: int,
        success_alpha: float,
        latency_alpha: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self._alpha = success_alpha
        self._latency_alpha = latency_alpha
        self._failure_threshold = failure_threshold
        self._cooldown_base_ms = cooldown_base_ms
        self._cooldown_max_ms = cooldown_max_ms
        self._probes = half_open_probes
        self._clock = clock
        self._states: dict[str, ProviderState] = {c.id: ProviderState(config=c) for c in configs}

    def states(self) -> dict[str, ProviderState]:
        """Return the provider state mapping."""
        return self._states

    def get(self, provider_id: str) -> ProviderState | None:
        """Return the state of a provider by id."""
        return self._states.get(provider_id)

    def replace(self, configs: list[ProviderConfig]) -> None:
        """Rebuild states, preserving statistics of providers that still exist."""
        previous = self._states
        self._states = {
            cfg.id: ProviderState(config=cfg, stats=self._stats_for(previous, cfg)) for cfg in configs
        }

    @staticmethod
    def _stats_for(previous: dict[str, ProviderState], config: ProviderConfig) -> ProviderStats:
        """Reuse existing statistics for a provider that survives a reload."""
        existing = previous.get(config.id)
        return existing.stats if existing is not None else ProviderStats()

    def available(self, provider_id: str, now: float | None = None) -> bool:
        """Report whether a provider's circuit currently admits traffic."""
        state = self._states.get(provider_id)
        if state is None:
            return False
        moment = now if now is not None else self._clock()
        if state.state is CircuitState.OPEN:
            if moment < state.opened_until:
                return False
            state.state = CircuitState.HALF_OPEN
            state.probes_left = self._probes
        if state.state is CircuitState.HALF_OPEN:
            return state.probes_left > 0
        return True

    def record_success(self, provider_id: str, latency_ms: float, cache_hit: bool) -> None:
        """Record a successful call and close an open circuit."""
        state = self._states.get(provider_id)
        if state is None:
            return
        state.stats.record_success(latency_ms, self._alpha, cache_hit, self._latency_alpha)
        state.state = CircuitState.CLOSED
        state.opened_until = 0.0
        state.probes_left = 0

    def record_failure(self, provider_id: str, error: str) -> None:
        """Record a failed call and trip the circuit when the threshold is reached."""
        state = self._states.get(provider_id)
        if state is None:
            return
        state.stats.record_failure(error, self._alpha)
        if state.state is CircuitState.HALF_OPEN:
            state.probes_left -= 1
            if state.probes_left <= 0:
                self._open(state)
            return
        if state.stats.consecutive_failures >= self._failure_threshold:
            self._open(state)

    def _open(self, state: ProviderState) -> None:
        """Trip a provider circuit with exponential cooldown."""
        exponent = min(state.stats.consecutive_failures - self._failure_threshold, 10)
        delay_ms = min(self._cooldown_base_ms * (2 ** max(exponent, 0)), self._cooldown_max_ms)
        state.state = CircuitState.OPEN
        state.opened_until = self._clock() + delay_ms / 1000.0
        state.probes_left = self._probes

    def snapshot(self) -> list[dict[str, object]]:
        """Serialize provider health for the admin API."""
        now = self._clock()
        result: list[dict[str, object]] = []
        for state in self._states.values():
            result.append(
                {
                    "id": state.config.id,
                    "state": state.state.value,
                    "success_rate": round(state.stats.success_rate, 4),
                    "latency_ms": round(state.stats.latency_ms, 2),
                    "cache_hit_rate": round(state.stats.cache_hit_rate, 4),
                    "calls": state.stats.total_calls,
                    "failures": state.stats.total_failures,
                    "cooldown_seconds": max(0.0, round(state.opened_until - now, 2)),
                    "inflight": state.inflight,
                    "capacity": state.capacity(),
                    "enabled": state.config.enabled,
                }
            )
        return result
