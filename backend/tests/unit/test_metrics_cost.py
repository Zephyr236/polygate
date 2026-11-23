"""Tests for cache savings accounting."""

from __future__ import annotations

from polygate.config import ProviderConfig
from polygate.metrics import cache_savings
from polygate.protocols.base import Usage


def _config() -> ProviderConfig:
    return ProviderConfig.model_validate(
        {
            "id": "p",
            "base_url": "https://x",
            "model": "m",
            "api_key_env": "K",
            "input_price_per_mtok": 0.15,
            "cost_coefficient": 2.0,
        }
    )


def test_cache_savings_includes_cost_coefficient_and_multiplier() -> None:
    usage = Usage(cache_read_tokens=1000)
    expected = round(1000 * 0.15 * 0.9 * 2.0 * 1.5 / 1_000_000, 8)
    assert cache_savings(_config(), usage, 1.5) == expected


def test_cache_savings_zero_without_cached_tokens() -> None:
    assert cache_savings(_config(), Usage(), 1.0) == 0.0
