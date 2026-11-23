"""Tests for routing score computation and candidate ranking."""

from __future__ import annotations

import pytest

from polygate.config import ProviderConfig, RoutingConfig, RoutingWeights
from polygate.routing.scorer import (
    ScoreBreakdown,
    cost_component,
    normalize_cost_scores,
    rank_candidates,
    score_provider,
    speed_component,
)
from polygate.routing.state import ProviderState, ProviderStats


def _config(provider_id: str, **overrides: object) -> ProviderConfig:
    base = {"id": provider_id, "base_url": "https://x", "model": "m", "api_key_env": "K"}
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def _state(config: ProviderConfig, **stats: float) -> ProviderState:
    return ProviderState(config=config, stats=ProviderStats(**stats))  # type: ignore[arg-type]


def test_speed_component_bounds() -> None:
    assert speed_component(0.0, 2500.0) == 1.0
    assert speed_component(2500.0, 2500.0) == 1.0
    assert speed_component(5000.0, 2500.0) == 0.5
    assert speed_component(1_000_000.0, 2500.0) == pytest.approx(0.0025)


def test_cost_component_inverts_coefficient_and_multiplier() -> None:
    config = _config("a", cost_coefficient=0.5)
    assert cost_component(config, 2.0) == pytest.approx(1.0)
    assert cost_component(config, 1.0) == pytest.approx(2.0)


def test_score_provider_uses_weights() -> None:
    config = _config("a", cost_coefficient=1.0)
    state = _state(config, success_rate=0.8, latency_ms=1250.0, cache_hit_rate=0.4)
    routing = RoutingConfig(weights=RoutingWeights(success=0.5, speed=0.25, cost=0.2, cache=0.05))
    score = score_provider(config, state, routing, 1.0)
    assert score.success == 0.8
    assert score.speed == 1.0
    assert score.cache == 0.4
    assert score.cost == 1.0
    expected = 0.5 * 0.8 + 0.25 * 1.0 + 0.2 * 1.0 + 0.05 * 0.4
    assert score.total == pytest.approx(expected)
    assert score.priority == 1


def test_normalize_cost_scores_scales_to_peak() -> None:
    items = [
        ScoreBreakdown("a", 1.0, 1.0, 4.0, 0.0, 5.0, 1),
        ScoreBreakdown("b", 1.0, 1.0, 2.0, 0.0, 3.0, 1),
    ]
    scaled = normalize_cost_scores(items)
    assert scaled[0].cost == 1.0
    assert scaled[1].cost == 0.5
    assert scaled[0].total == 5.0


def test_normalize_cost_scores_empty_and_zero_peak() -> None:
    assert normalize_cost_scores([]) == []
    items = [ScoreBreakdown("a", 1.0, 1.0, 0.0, 0.0, 1.0, 1)]
    assert normalize_cost_scores(items) == items


def test_rank_candidates_orders_by_priority_then_score() -> None:
    configs = [
        _config("slow", cost_coefficient=1.0, priority=1),
        _config("fast", cost_coefficient=1.0, priority=1),
        _config("premium", cost_coefficient=1.0, priority=0),
    ]
    states = {
        "slow": _state(configs[0], success_rate=0.9, latency_ms=5000.0),
        "fast": _state(configs[1], success_rate=0.3, latency_ms=100.0, cache_hit_rate=1.0),
        "premium": _state(configs[2], success_rate=0.5, latency_ms=100.0),
    }
    routing = RoutingConfig()
    ranked = rank_candidates(configs, states, routing, 12, 1)
    assert ranked[0].provider_id == "premium"
    assert {item.provider_id for item in ranked[1:]} == {"fast", "slow"}
    assert ranked[0].priority == 0


def test_rank_candidates_excludes_disabled_inactive_and_unknown() -> None:
    active = _config("active")
    disabled = _config("disabled", enabled=False)
    inactive = _config("inactive", active_windows=[{"start_hour": 1, "end_hour": 2}])
    configs = [active, disabled, inactive, _config("stateless")]
    states = {"active": _state(active), "disabled": _state(disabled), "inactive": _state(inactive)}
    ranked = rank_candidates(configs, states, RoutingConfig(), 12, 1)
    assert [item.provider_id for item in ranked] == ["active"]
    ranked = rank_candidates(configs, states, RoutingConfig(), 12, 1, exclude={"active"})
    assert ranked == []


def test_rank_candidates_applies_time_multiplier() -> None:
    cheap = _config("cheap", cost_coefficient=2.0)
    pricey = _config(
        "pricey", cost_coefficient=1.0, active_windows=[{"start_hour": 0, "end_hour": 24, "multiplier": 4.0}]
    )
    configs = [cheap, pricey]
    states = {"cheap": _state(cheap), "pricey": _state(pricey)}
    routed_current = rank_candidates(configs, states, RoutingConfig(), 12, 1)
    assert routed_current[0].provider_id == "cheap"
