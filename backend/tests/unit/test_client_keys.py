"""Tests for caller keys, provider allowlists and per-key routing weights."""

from __future__ import annotations

import pytest

from polygate.config import (
    ClientPolicy,
    ConfigError,
    ProviderConfig,
    RoutingConfig,
    RoutingWeights,
    build_app_config,
)
from polygate.routing.scorer import rank_candidates
from polygate.routing.state import HealthRegistry


def _provider(provider_id: str, coefficient: float = 1.0) -> dict[str, object]:
    return {
        "id": provider_id,
        "base_url": "https://x",
        "model": "m",
        "api_key_env": "K",
        "cost_coefficient": coefficient,
    }


def test_client_key_selects_providers_and_weights() -> None:
    config = build_app_config(
        {
            "provider": [_provider("a"), _provider("b")],
            "client_key": [
                {
                    "id": "team-a",
                    "name": "Team A",
                    "api_key_env": "TEAM_A_KEY",
                    "allowed_providers": ["a"],
                    "weights": {"success": 1.0, "speed": 0, "cost": 0, "cache": 0},
                }
            ],
        },
        {"TEAM_A_KEY": "team-a-secret"},
    )
    key = config.client_keys[0]
    assert key.id == "team-a"
    assert key.allowed_providers == ["a"]
    assert key.weights == RoutingWeights(success=1.0, speed=0, cost=0, cache=0)


def test_client_key_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [{"id": "team-a", "api_key_env": "TEAM_A_KEY"}],
            },
            {},
        )


def test_unknown_provider_in_client_key_is_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown providers"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [{"id": "team-a", "api_key_env": "TEAM_A_KEY", "allowed_providers": ["missing"]}],
            },
            {},
        )


def test_duplicate_key_env_is_rejected() -> None:
    with pytest.raises(ConfigError, match="distinct api_key_env"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [
                    {"id": "one", "api_key_env": "SAME", "allowed_providers": ["a"]},
                    {"id": "two", "api_key_env": "SAME", "allowed_providers": ["a"]},
                ],
            },
            {"SAME": "secret"},
        )


def test_legacy_env_name_is_rejected_for_client_key() -> None:
    with pytest.raises(ConfigError, match="PROXY_API_KEY"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [
                    {"id": "one", "api_key_env": "PROXY_API_KEY", "allowed_providers": ["a"]}
                ],
            },
            {"PROXY_API_KEY": "legacy"},
        )


def test_duplicate_key_values_are_rejected() -> None:
    with pytest.raises(ConfigError, match="env values must be distinct"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [
                    {"id": "one", "api_key_env": "ONE", "allowed_providers": ["a"]},
                    {"id": "two", "api_key_env": "TWO", "allowed_providers": ["a"]},
                ],
            },
            {"ONE": "same", "TWO": "same"},
        )


def test_legacy_key_collision_is_rejected() -> None:
    with pytest.raises(ConfigError, match="legacy PROXY_API_KEY"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [
                    {"id": "one", "api_key_env": "ONE", "allowed_providers": ["a"]}
                ],
            },
            {"ONE": "same", "PROXY_API_KEY": "same"},
        )


def test_unprovisioned_client_keys_fail_closed_at_startup() -> None:
    with pytest.raises(ConfigError, match="no api_key_env is set"):
        build_app_config(
            {
                "provider": [_provider("a")],
                "client_key": [
                    {"id": "one", "api_key_env": "MISSING", "allowed_providers": ["a"]}
                ],
            },
            {},
        )


def test_policy_without_allowlist_allows_all() -> None:
    policy = ClientPolicy("open")
    assert policy.allows("a")
    assert policy.allows("b")


def test_policy_allowlist_is_enforced() -> None:
    policy = ClientPolicy("team", frozenset({"b"}))
    assert not policy.allows("a")
    assert policy.allows("b")


def test_rank_candidates_applies_per_key_weights() -> None:
    configs = [
        ProviderConfig.model_validate(_provider("cheap", 1.0)),
        ProviderConfig.model_validate(_provider("reliable", 10.0)),
    ]
    health = HealthRegistry(
        configs,
        failure_threshold=3,
        cooldown_base_ms=1000,
        cooldown_max_ms=10_000,
        half_open_probes=1,
        success_alpha=0.5,
        latency_alpha=0.5,
    )
    health.states()["cheap"].stats.success_rate = 0.1
    health.states()["reliable"].stats.success_rate = 1.0
    cost_weights = RoutingWeights(success=0, speed=0, cost=1.0, cache=0)
    success_weights = RoutingWeights(success=1.0, speed=0, cost=0, cache=0)
    cheap_routing = RoutingConfig(weights=cost_weights)
    reliable_routing = RoutingConfig(weights=success_weights)
    cheap = rank_candidates(configs, health.states(), cheap_routing, 12, 1)
    reliable = rank_candidates(configs, health.states(), reliable_routing, 12, 1)
    assert cheap[0].provider_id == "cheap"
    assert reliable[0].provider_id == "reliable"
    priority_configs = [
        ProviderConfig.model_validate(_provider("first", 10.0) | {"priority": 0}),
        ProviderConfig.model_validate(_provider("cheap", 1.0) | {"priority": 1}),
    ]
    priority_health = HealthRegistry(
        priority_configs,
        failure_threshold=3,
        cooldown_base_ms=1000,
        cooldown_max_ms=10_000,
        half_open_probes=1,
        success_alpha=0.5,
        latency_alpha=0.5,
    )
    default_rank = rank_candidates(priority_configs, priority_health.states(), cheap_routing, 12, 1)
    flattened = rank_candidates(
        priority_configs, priority_health.states(), cheap_routing, 12, 1, respect_priority=False
    )
    assert default_rank[0].provider_id == "first"
    assert flattened[0].provider_id == "cheap"
