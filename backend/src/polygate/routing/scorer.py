"""Pure routing score computation and candidate filtering."""

from __future__ import annotations

from dataclasses import dataclass

from polygate.config import ProviderConfig, RoutingConfig
from polygate.routing.state import ProviderState


@dataclass(frozen=True)
class ScoreBreakdown:
    """Score components for one provider candidate."""

    provider_id: str
    success: float
    speed: float
    cost: float
    cache: float
    total: float
    priority: int


def speed_component(latency_ms: float, target_ms: float) -> float:
    """Normalize latency into a 0..1 speed score."""
    if latency_ms <= 0:
        return 1.0
    return max(0.0, min(1.0, target_ms / latency_ms))


def cost_component(config: ProviderConfig, multiplier: float) -> float:
    """Return the inverse-cost score for a provider."""
    return 1.0 / (config.cost_coefficient * multiplier)


def score_provider(
    config: ProviderConfig,
    stats: ProviderState,
    routing: RoutingConfig,
    multiplier: float,
) -> ScoreBreakdown:
    """Compute the routing score of one candidate."""
    weights = routing.weights
    success = stats.stats.success_rate
    speed = speed_component(stats.stats.latency_ms, routing.speed_target_ms)
    cost = cost_component(config, multiplier)
    cache = stats.stats.cache_hit_rate
    total = weights.success * success + weights.speed * speed + weights.cost * cost + weights.cache * cache
    return ScoreBreakdown(
        provider_id=config.id,
        success=success,
        speed=speed,
        cost=cost,
        cache=cache,
        total=total,
        priority=config.priority,
    )


def normalize_cost_scores(breakdowns: list[ScoreBreakdown]) -> list[ScoreBreakdown]:
    """Rescale cost components so the cheapest candidate scores 1.0."""
    if not breakdowns:
        return []
    peak = max(item.cost for item in breakdowns)
    if peak <= 0:
        return breakdowns
    return [
        ScoreBreakdown(
            provider_id=item.provider_id,
            success=item.success,
            speed=item.speed,
            cost=item.cost / peak,
            cache=item.cache,
            total=item.total,
            priority=item.priority,
        )
        for item in breakdowns
    ]


def _eligible(config: ProviderConfig, states: dict[str, ProviderState], hour: int, weekday: int) -> bool:
    """Report whether a provider may be scored in the given time window."""
    if not config.enabled or config.id not in states:
        return False
    return config.is_active_at(hour, weekday)


def rank_candidates(
    configs: list[ProviderConfig],
    states: dict[str, ProviderState],
    routing: RoutingConfig,
    hour: int,
    weekday: int,
    exclude: set[str] | None = None,
) -> list[ScoreBreakdown]:
    """Rank eligible providers by score, keeping priority tiers contiguous."""
    excluded = exclude or set()
    scored = [
        score_provider(config, states[config.id], routing, config.multiplier_at(hour, weekday))
        for config in configs
        if config.id not in excluded and _eligible(config, states, hour, weekday)
    ]
    return sorted(normalize_cost_scores(scored), key=lambda item: (item.priority, -item.total))
