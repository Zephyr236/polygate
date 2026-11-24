"""Health, readiness and Prometheus exposition endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from polygate.api.deps import gateway_of
from polygate.gateway import Gateway

router = APIRouter(tags=["health"])


def _usable_providers(gateway: Gateway) -> list[str]:
    return [
        config.id for config in gateway.providers if config.enabled and gateway.keys.get(config.api_key_env)
    ]


def _readiness_payload(usable: list[str], proxy_auth: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ready" if usable and proxy_auth else "degraded",
        "usable_providers": usable,
        "proxy_auth_ready": proxy_auth,
    }
    if not proxy_auth:
        payload["reason"] = "no proxy credential"
    return payload


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Report process liveness."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """Report whether providers and proxy authentication are usable."""
    gateway = gateway_of(request)
    usable = _usable_providers(gateway)
    proxy_auth = gateway.config.proxy_auth_configured
    ready = bool(usable) and proxy_auth
    return JSONResponse(_readiness_payload(usable, proxy_auth), status_code=200 if ready else 503)


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
