"""Application container holding provider configs, scheduler, health and metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from polygate.config import AppConfig, ProviderConfig, RoutingConfig
from polygate.metrics import estimate_cost
from polygate.protocols.base import InternalRequest, InternalResponse, Usage
from polygate.providers.base import BaseProvider, build_provider
from polygate.routing.scheduler import RouteResult, Scheduler, utc_hour_weekday
from polygate.routing.state import HealthRegistry
from polygate.storage import MetricRecord, MetricsStore


@dataclass
class Gateway:
    """Runtime gateway state shared by API handlers."""

    config: AppConfig
    store: MetricsStore
    client: httpx.AsyncClient
    health: HealthRegistry
    scheduler: Scheduler
    keys: dict[str, str] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    providers: list[ProviderConfig] = field(default_factory=list)


def build_health(configs: list[ProviderConfig], routing: RoutingConfig) -> HealthRegistry:
    """Construct a health registry from provider configs and routing policy."""
    return HealthRegistry(
        configs,
        failure_threshold=routing.failure_threshold,
        cooldown_base_ms=routing.cooldown_base_ms,
        cooldown_max_ms=routing.cooldown_max_ms,
        half_open_probes=routing.half_open_probes,
        success_alpha=routing.success_ema_alpha,
        latency_alpha=routing.latency_ema_alpha,
    )


def build_gateway(
    config: AppConfig, store: MetricsStore, client: httpx.AsyncClient, keys: dict[str, str]
) -> Gateway:
    """Assemble the gateway with a scheduler bound to the live pool."""
    health = build_health(config.providers, config.routing)
    providers = list(config.providers)

    def factory(provider_config: ProviderConfig, api_key: str) -> BaseProvider:
        """Build an upstream adapter bound to the shared HTTP client."""
        return build_provider(provider_config, api_key, client)

    scheduler = Scheduler(providers, config.routing, health, factory)
    return Gateway(
        config=config,
        store=store,
        client=client,
        health=health,
        scheduler=scheduler,
        keys=keys,
        providers=providers,
    )


def replace_providers(gateway: Gateway, providers: list[ProviderConfig]) -> None:
    """Swap the live provider pool and rebuild health states."""
    gateway.providers = providers
    gateway.health.replace(providers)
    gateway.scheduler.providers = providers
    gateway.scheduler.prune_adapters({provider.id for provider in providers})


def cost_for(gateway: Gateway, provider_id: str, usage: Usage) -> float:
    """Estimate the cost of a call with the provider cost settings."""
    hour, weekday = utc_hour_weekday()
    for provider in gateway.providers:
        if provider.id == provider_id:
            return estimate_cost(provider, usage, provider.multiplier_at(hour, weekday))
    return 0.0


async def record_route_result(gateway: Gateway, request: InternalRequest, route: RouteResult) -> None:
    """Persist metrics and events for a completed non-streaming call."""
    response: InternalResponse = route.result.response
    usage = response.usage
    await gateway.store.record(
        MetricRecord(
            provider_id=response.provider_id,
            model=request.model,
            ok=True,
            error_class=None,
            latency_ms=route.result.latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cost=cost_for(gateway, response.provider_id, usage),
            switched=len(route.attempts),
        )
    )
    for attempt in route.attempts:
        await gateway.store.add_event(
            "switch", attempt.provider_id, f"{attempt.error_class}: {attempt.detail[:160]}"
        )


async def record_stream_result(
    gateway: Gateway, request: InternalRequest, provider_id: str, usage: Usage, switched: int, ok: bool
) -> None:
    """Persist metrics for a completed streaming call."""
    await gateway.store.record(
        MetricRecord(
            provider_id=provider_id,
            model=request.model,
            ok=ok,
            error_class=None if ok else "stream_error",
            latency_ms=0.0,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cost=cost_for(gateway, provider_id, usage),
            switched=switched,
        )
    )
