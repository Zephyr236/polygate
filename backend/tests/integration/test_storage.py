"""Tests for cost estimation, summaries and the metrics store."""

from __future__ import annotations

import pytest

from polygate.config import ProviderConfig
from polygate.metrics import estimate_cost, summarize
from polygate.protocols.base import Usage
from polygate.storage import MetricRecord, MetricsStore


def _config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "id": "p",
        "base_url": "https://x",
        "model": "m",
        "api_key_env": "K",
        "input_price_per_mtok": 0.15,
        "output_price_per_mtok": 0.6,
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def test_estimate_cost_applies_cache_discount_and_multiplier() -> None:
    config = _config()
    usage = Usage(prompt_tokens=1000, completion_tokens=500, cache_read_tokens=400)
    cost = estimate_cost(config, usage, 2.0)
    expected = ((600 * 0.15 + 400 * 0.015 + 500 * 0.6) / 1_000_000) * 2.0
    assert cost == pytest.approx(expected, rel=1e-6)


def test_estimate_cost_zero_tokens() -> None:
    assert estimate_cost(_config(), Usage(), 1.0) == 0.0


def test_summarize_aggregates_rows() -> None:
    rows = [
        {
            "calls": 10,
            "failures": 2,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cache_read_tokens": 20,
            "cost": 0.5,
        },
        {
            "calls": 5,
            "failures": 0,
            "prompt_tokens": 60,
            "completion_tokens": 30,
            "cache_read_tokens": 10,
            "cost": 0.25,
        },
    ]
    summary = summarize(rows, {"a": _config(), "b": _config(id="b")})
    assert summary["calls"] == 15
    assert summary["failures"] == 2
    assert summary["success_rate"] == pytest.approx(13 / 15, abs=1e-4)
    assert summary["cache_hit_rate"] == pytest.approx(30 / 160, abs=1e-4)
    assert summary["cost_usd"] == 0.75
    assert summary["providers"] == 2


def test_summarize_empty() -> None:
    summary = summarize([], {})
    assert summary["calls"] == 0
    assert summary["success_rate"] == 0.0
    assert summary["cache_hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_store_record_and_overview(tmp_path: object) -> None:
    store = MetricsStore(str(tmp_path / "m.db"))  # type: ignore[operator]
    await store.open()
    await store.record(
        MetricRecord(
            provider_id="p",
            model="m",
            ok=True,
            error_class=None,
            latency_ms=120.0,
            prompt_tokens=10,
            completion_tokens=5,
            reasoning_tokens=0,
            cache_read_tokens=4,
            cost=0.001,
            switched=1,
        )
    )
    await store.record(
        MetricRecord(
            provider_id="p",
            model="m",
            ok=False,
            error_class="timeout",
            latency_ms=400.0,
            prompt_tokens=0,
            completion_tokens=0,
            reasoning_tokens=0,
            cache_read_tokens=0,
            cost=0.0,
        )
    )
    rows = await store.overview(3600)
    assert rows[0]["calls"] == 2
    assert rows[0]["ok"] == 1
    assert rows[0]["failures"] == 1
    assert rows[0]["cost"] == pytest.approx(0.001)
    series = await store.timeseries(3600, 60)
    assert len(series) == 1
    await store.close()


@pytest.mark.asyncio
async def test_store_events_and_provider_overrides(tmp_path: object) -> None:
    store = MetricsStore(str(tmp_path / "m.db"))  # type: ignore[operator]
    await store.open()
    await store.add_event("switch", "p", "timeout")
    events = await store.recent_events(10)
    assert events[0]["kind"] == "switch"
    await store.save_provider("p", '{"id":"p"}')
    assert await store.list_providers() == [{"id": "p", "payload": '{"id":"p"}'}]
    await store.save_provider("p", '{"id":"p2"}')
    assert (await store.list_providers())[0]["payload"] == '{"id":"p2"}'
    await store.delete_provider("p")
    assert await store.list_providers() == []
    await store.close()


@pytest.mark.asyncio
async def test_store_requires_open(tmp_path: object) -> None:
    store = MetricsStore(str(tmp_path / "m.db"))  # type: ignore[operator]
    with pytest.raises(RuntimeError):
        await store.overview(3600)
    await store.open()
    await store.close()
    await store.close()
