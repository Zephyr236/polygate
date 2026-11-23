"""Tests for health registry statistics, lanes and breaker transitions."""

from __future__ import annotations

import pytest

from polygate.config import ProviderConfig
from polygate.routing.state import CircuitState, HealthRegistry, ProviderState, ProviderStats


def _config(provider_id: str = "p", **overrides: object) -> ProviderConfig:
    base = {"id": provider_id, "base_url": "https://x", "model": "m", "api_key_env": "K"}
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def _registry(configs: list[ProviderConfig], **overrides: float) -> HealthRegistry:
    params: dict[str, float] = {
        "failure_threshold": 3,
        "cooldown_base_ms": 1000,
        "cooldown_max_ms": 10_000,
        "half_open_probes": 1,
        "success_alpha": 0.5,
        "latency_alpha": 0.5,
    }
    params.update(overrides)
    return HealthRegistry(configs, **params)  # type: ignore[arg-type]


def test_stats_moving_averages() -> None:
    stats = ProviderStats(success_rate=0.5)
    stats.record_success(100.0, 0.5, True, 0.5)
    assert stats.success_rate == 0.75
    assert stats.latency_ms == 50.0
    assert stats.cache_hit_rate == 0.5
    stats.record_failure("boom", 0.5)
    assert stats.success_rate == pytest.approx(0.375)

    assert stats.consecutive_failures == 1
    stats.record_success(200.0, 0.5, False, 0.5)
    assert stats.consecutive_failures == 0
    assert stats.latency_ms == 125.0


def test_state_acquire_saturation_and_release() -> None:
    state = ProviderState(config=_config(max_concurrency=2))
    assert state.acquire() == 0
    assert state.acquire() == 0
    assert state.inflight == 2
    assert state.acquire() is None
    state.release(0)
    assert state.inflight == 1
    assert state.acquire() == 0


def test_state_acquire_multiple_lanes() -> None:
    state = ProviderState(config=_config(max_concurrency=1, lanes=3))
    lanes = [state.acquire() for _ in range(3)]
    assert lanes == [0, 1, 2]
    assert state.acquire() is None
    state.release(1)
    assert state.acquire() == 1


def test_stats_success_rate_uses_alpha() -> None:
    stats = ProviderStats()
    stats.record_failure("e", 0.3)
    assert stats.success_rate == pytest.approx(0.7)


def test_failure_threshold_opens_circuit_and_cooldown() -> None:
    clock = [100.0]
    registry = _registry([_config()], clock=lambda: clock[0])
    for _ in range(3):
        registry.record_failure("p", "server_error")
    state = registry.get("p")
    assert state is not None
    assert state.state is CircuitState.OPEN
    assert state.opened_until == pytest.approx(101.0)
    assert not registry.available("p", 100.5)


def test_half_open_after_cooldown() -> None:
    clock = [100.0]
    registry = _registry([_config()], clock=lambda: clock[0])
    for _ in range(3):
        registry.record_failure("p", "server_error")
    clock[0] = 101.0
    assert registry.available("p", 101.0)
    assert registry.get("p").state is CircuitState.HALF_OPEN  # type: ignore[union-attr]


def test_half_open_probe_failure_reopens() -> None:
    clock = [100.0]
    registry = _registry([_config()], clock=lambda: clock[0])
    for _ in range(3):
        registry.record_failure("p", "server_error")
    clock[0] = 101.5
    registry.available("p", 101.5)
    registry.record_failure("p", "timeout")
    assert registry.get("p").state is CircuitState.OPEN  # type: ignore[union-attr]


def test_half_open_success_closes() -> None:
    clock = [100.0]
    registry = _registry([_config()], clock=lambda: clock[0])
    for _ in range(3):
        registry.record_failure("p", "server_error")
    clock[0] = 102.0
    registry.available("p")
    registry.record_success("p", 50.0, True)
    assert registry.get("p").state is CircuitState.CLOSED  # type: ignore[union-attr]


def test_cooldown_exponential_capped() -> None:
    clock = [0.0]
    registry = _registry([_config()], clock=lambda: clock[0], half_open_probes=1)
    for _ in range(3):
        registry.record_failure("p", "err")
    for _ in range(10):
        clock[0] = registry.get("p").opened_until  # type: ignore[union-attr]
        registry.available("p")
        registry.record_failure("p", "err")
    assert registry.get("p").opened_until <= 10.0 + clock[0]  # type: ignore[union-attr]


def test_unknown_provider_is_unavailable() -> None:
    registry = _registry([_config()])
    assert not registry.available("missing")
    registry.record_success("nope", 1.0, False)
    registry.record_failure("nope", "x")


def test_replace_preserves_stats() -> None:
    registry = _registry([_config()])
    registry.record_success("p", 120.0, True)
    registry.replace([_config(lanes=2, max_concurrency=3)])
    state = registry.get("p")
    assert state is not None
    assert state.stats.total_calls == 1
    assert len(state.lane_inflight) == 2
    registry.replace([_config("other")])
    assert registry.get("p") is None
    assert registry.get("other") is not None


def test_snapshot_fields() -> None:
    registry = _registry([_config()])
    snapshot = registry.snapshot()
    assert snapshot[0]["id"] == "p"
    assert snapshot[0]["state"] == "closed"
    assert snapshot[0]["capacity"] == 8


def test_acquire_capacity_boundary_exact() -> None:
    state = ProviderState(config=_config(max_concurrency=1, lanes=1))
    assert state.acquire() == 0
    assert state.inflight == 1
    assert state.acquire() is None


def test_release_never_goes_negative() -> None:
    state = ProviderState(config=_config(max_concurrency=2))
    state.release(0)
    assert state.inflight == 0
    assert state.lane_inflight[0] == 0


def test_record_failure_counters() -> None:
    stats = ProviderStats()
    stats.record_failure("boom", 0.5)
    assert stats.total_calls == 1
    assert stats.total_failures == 1
    assert stats.last_error == "boom"
    stats.record_failure("boom2", 0.5)
    assert stats.total_calls == 2
    assert stats.total_failures == 2


def test_record_success_counters() -> None:
    stats = ProviderStats()
    stats.record_success(10.0, 0.5, True, 0.5)
    stats.record_success(20.0, 0.5, False, 0.5)
    assert stats.total_calls == 2
    assert stats.total_failures == 0


def test_snapshot_exact_keys_and_values() -> None:
    clock = [50.0]
    registry = _registry([_config()], clock=lambda: clock[0])
    registry.record_failure("p", "server_error")
    registry.record_failure("p", "server_error")
    registry.record_failure("p", "server_error")
    row = registry.snapshot()[0]
    assert set(row) == {
        "id",
        "state",
        "success_rate",
        "latency_ms",
        "cache_hit_rate",
        "calls",
        "failures",
        "cooldown_seconds",
        "inflight",
        "capacity",
        "enabled",
    }
    assert row["calls"] == 3
    assert row["failures"] == 3
    assert row["cooldown_seconds"] == pytest.approx(1.0)
    assert row["enabled"] is True
