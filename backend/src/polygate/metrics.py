"""Cost estimation and dashboard aggregation helpers."""

from __future__ import annotations

from typing import Any

from polygate.config import ProviderConfig
from polygate.protocols.base import Usage


def estimate_cost(config: ProviderConfig, usage: Usage, multiplier: float) -> float:
    """Estimate the USD cost of one call from token counts and provider prices."""
    input_tokens = max(usage.prompt_tokens - usage.cache_read_tokens, 0)
    base = (
        input_tokens * config.input_price_per_mtok
        + usage.cache_read_tokens * config.input_price_per_mtok * 0.1
        + usage.completion_tokens * config.output_price_per_mtok
    ) / 1_000_000
    return round(base * config.cost_coefficient * multiplier, 8)


def cache_savings(config: ProviderConfig, usage: Usage, multiplier: float) -> float:
    """Estimate the USD saved by cached prompt tokens, including the cost settings."""
    base = usage.cache_read_tokens * config.input_price_per_mtok * 0.9
    return round(base * config.cost_coefficient * multiplier / 1_000_000, 8)


def _total(rows: list[dict[str, Any]], key: str) -> int:
    """Sum one integer column across metric rows."""
    return sum(int(row.get(key) or 0) for row in rows)


def _ratio(numerator: int, denominator: int) -> float:
    """Return a rounded ratio that yields zero for empty denominators."""
    return round(numerator / denominator, 4) if denominator else 0.0


def summarize(rows: list[dict[str, Any]], configs: dict[str, ProviderConfig]) -> dict[str, Any]:
    """Aggregate gateway-wide totals from per-provider metric rows."""
    calls = _total(rows, "calls")
    failures = _total(rows, "failures")
    prompt_tokens = _total(rows, "prompt_tokens")
    return {
        "calls": calls,
        "failures": failures,
        "success_rate": _ratio(calls - failures, calls),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": _total(rows, "completion_tokens"),
        "cache_hit_rate": _ratio(_total(rows, "cache_read_tokens"), prompt_tokens),
        "cost_usd": round(sum(float(row.get("cost") or 0) for row in rows), 6),
        "providers": len(configs),
    }
