"""Health, readiness and Prometheus exposition endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from polygate.api.deps import gateway_of

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Report process liveness."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, object]:
    """Report whether at least one provider is usable."""
    gateway = gateway_of(request)
    usable = [
        config.id for config in gateway.providers if config.enabled and gateway.keys.get(config.api_key_env)
    ]
    return {"status": "ready" if usable else "degraded", "usable_providers": usable}


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def prometheus(request: Request) -> str:
    """Expose provider health gauges in Prometheus text format."""
    gateway = gateway_of(request)
    lines = [
        "# HELP polygate_provider_success_rate EMA success rate per provider",
        "# TYPE polygate_provider_success_rate gauge",
    ]
    for state in gateway.health.snapshot():
        lines.append(f'polygate_provider_success_rate{{provider="{state["id"]}"}} {state["success_rate"]}')
    lines += [
        "# HELP polygate_provider_inflight Current occupied concurrency slots",
        "# TYPE polygate_provider_inflight gauge",
    ]
    for state in gateway.health.snapshot():
        lines.append(f'polygate_provider_inflight{{provider="{state["id"]}"}} {state["inflight"]}')
    return "\n".join(lines) + "\n"
