"""Tests for configuration parsing and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polygate.config import (
    AuthStyle,
    ConfigError,
    ProviderConfig,
    RoutingConfig,
    SessionMode,
    StreamUsage,
    TimeWindow,
    build_app_config,
    load_app_config,
    parse_providers_document,
)


def _provider(**overrides: object) -> ProviderConfig:
    base = {"id": "amr", "base_url": "https://example.com", "model": "m", "api_key_env": "K_API_KEY"}
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def test_provider_defaults() -> None:
    provider = _provider()
    assert provider.protocol.value == "openai"
    assert provider.auth_style is AuthStyle.BEARER
    assert provider.session_mode is SessionMode.NONE
    assert provider.stream_usage is StreamUsage.NONE
    assert provider.lanes == 1
    assert provider.max_concurrency == 8
    assert provider.is_active_at(12, 3)


def test_provider_requires_valid_id() -> None:
    with pytest.raises(ValidationError):
        _provider(id="Bad Id")


def test_provider_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderConfig.model_validate(
            {"id": "x", "base_url": "u", "model": "m", "api_key_env": "K", "unknown": 1}
        )


def test_api_key_resolution() -> None:
    provider = _provider()
    assert provider.api_key({"K_API_KEY": "secret"}) == "secret"
    assert provider.api_key({"K_API_KEY": ""}) is None
    assert provider.api_key({}) is None


def test_time_window_wrapping_and_weekday() -> None:
    window = TimeWindow(start_hour=22, end_hour=4, multiplier=2.0, weekday_from=1, weekday_to=7)
    assert window.contains(23, 3)
    assert window.contains(2, 3)
    assert not window.contains(12, 3)
    window = TimeWindow(start_hour=1, end_hour=4, weekday_from=2, weekday_to=3)
    assert window.contains(2, 2)
    assert not window.contains(2, 1)


def test_multiplier_and_active_window_lookup() -> None:
    provider = _provider(active_windows=[{"start_hour": 0, "end_hour": 24, "multiplier": 2.5}])
    assert provider.multiplier_at(5, 1) == 2.5
    assert provider.is_active_at(5, 1)
    provider = _provider(active_windows=[{"start_hour": 1, "end_hour": 2}])
    assert not provider.is_active_at(12, 1)
    assert provider.multiplier_at(12, 1) == 1.0


def test_parse_providers_requires_a_list() -> None:
    with pytest.raises(ConfigError):
        parse_providers_document({"provider": {"id": "x"}})


def test_parse_providers_validates_items() -> None:
    document = {"provider": [{"id": "a", "base_url": "u", "model": "m", "api_key_env": "K"}]}
    providers = parse_providers_document(document)
    assert providers[0].id == "a"


def test_build_app_config_reads_environment() -> None:
    document = {"provider": [{"id": "a", "base_url": "u", "model": "m", "api_key_env": "K"}], "routing": {}}
    env = {"ADMIN_TOKEN": "tok", "PROXY_API_KEY": "", "POLYGATE_DATABASE": "x.db"}
    config = build_app_config(document, env)
    assert config.admin_token == "tok"
    assert config.proxy_api_key is None
    assert str(config.database_path) == "x.db"
    assert isinstance(config.routing, RoutingConfig)


def test_build_app_config_empty_document() -> None:
    config = build_app_config({}, {})
    assert config.providers == []
    assert config.admin_token is None


def test_load_app_config_missing_file(tmp_path: object) -> None:
    with pytest.raises(ConfigError):
        load_app_config({"POLYGATE_CONFIG": "/nonexistent/file.toml"})


def test_load_app_config_invalid_toml(tmp_path: object) -> None:
    path = tmp_path / "bad.toml"  # type: ignore[operator]
    path.write_text("[provider\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_app_config({"POLYGATE_CONFIG": str(path)})


def test_routing_weights_require_positive_sum() -> None:
    with pytest.raises(ValidationError):
        RoutingConfig(weights={"success": 0.0, "speed": 0.0, "cost": 0.0, "cache": 0.0})
