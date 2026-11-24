"""Admin API for provider management, metrics and route simulation."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from polygate.api.auth import require_admin
from polygate.api.bodies import read_json
from polygate.api.deps import gateway_of
from polygate.config import ClientKeyConfig, ConfigError, ProviderConfig, validate_client_keys_against_providers
from polygate.gateway import Gateway, replace_providers
from polygate.metrics import summarize
from polygate.routing.scorer import rank_candidates

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_RANGES = {"15m": 900.0, "1h": 3600.0, "24h": 86400.0, "7d": 604800.0}
_BUCKETS = {"15m": 60, "1h": 300, "24h": 900, "7d": 3600}


def _since(range_name: str) -> tuple[float, int]:
    """Resolve a range name into window seconds and bucket width."""
    if range_name not in _RANGES:
        raise HTTPException(status_code=400, detail=f"unknown range: {range_name}")
    return _RANGES[range_name], _BUCKETS[range_name]


def _provider_body(config: ProviderConfig, keys: dict[str, str]) -> dict[str, Any]:
    """Serialize a provider config, exposing only secret presence."""
    body = config.model_dump(mode="json")
    body["api_key_configured"] = bool(keys.get(config.api_key_env))
    return body


def _client_body(key: ClientKeyConfig, keys: dict[str, str]) -> dict[str, Any]:
    """Serialize a caller key without its secret value."""
    body = key.model_dump(mode="json")
    body["key_configured"] = bool(keys.get(key.api_key_env))
    return body


@router.get("/clients")
async def list_clients(request: Request) -> dict[str, Any]:
    """List caller keys, provider allowlists and per-key routing weights."""
    gateway = gateway_of(request)
    return {
        "clients": [_client_body(key, gateway.keys) for key in gateway.config.client_keys],
        "legacy_key_configured": bool(gateway.config.proxy_api_key),
    }


@router.get("/providers")
async def list_providers(request: Request) -> dict[str, Any]:
    """List provider configs with secret-presence flags."""
    gateway = gateway_of(request)
    return {
        "providers": [_provider_body(config, gateway.keys) for config in gateway.providers],
        "health": gateway.health.snapshot(),
    }


@router.put("/providers")
async def upsert_providers(request: Request) -> dict[str, Any]:
    """Create or replace provider configs and persist the new pool."""
    body = await read_json(request)
    raw = body.get("providers")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="providers must be a list")
    gateway = gateway_of(request)
    try:
        configs = [ProviderConfig.model_validate(item) for item in raw]
        validate_client_keys_against_providers(gateway.config.client_keys, configs)
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=json.loads(error.json())) from error
    except ConfigError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    replace_providers(gateway, configs)
    for config in configs:
        await gateway.store.save_provider(config.id, config.model_dump_json())
    await gateway.store.add_event("config", None, f"providers updated: {len(configs)}")
    return {"providers": [_provider_body(config, gateway.keys) for config in gateway.providers]}


@router.get("/metrics")
async def metrics(request: Request, range: str = "1h") -> dict[str, Any]:
    """Return overview, per-provider rows and a time series for a range."""
    window, bucket = _since(range)
    gateway = gateway_of(request)
    rows = await gateway.store.overview(window)
    series = await gateway.store.timeseries(window, bucket)
    configs = {config.id: config for config in gateway.providers}
    return {
        "range": range,
        "overview": summarize(rows, configs),
        "providers": rows,
        "series": series,
        "health": gateway.health.snapshot(),
    }


@router.get("/events")
async def events(request: Request, limit: int = 50) -> dict[str, Any]:
    """Return recent operational events."""
    gateway = gateway_of(request)
    return {"events": await gateway.store.recent_events(min(limit, 200))}


async def snapshot_payload(gateway: Gateway) -> dict[str, Any]:
    """Build the SSE metrics snapshot body for one tick."""
    rows = await gateway.store.overview(900.0)
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "providers": rows,
        "health": gateway.health.snapshot(),
    }


async def metrics_events(gateway: Gateway) -> Any:
    """Yield metrics snapshots as SSE frames every two seconds."""
    while True:
        payload = await snapshot_payload(gateway)
        yield f"data: {json.dumps(payload, default=str)}\n\n"
        await asyncio.sleep(2.0)


@router.get("/metrics/stream")
async def metrics_stream(request: Request) -> StreamingResponse:
    """Push a metrics snapshot every two seconds as server-sent events."""
    gateway = gateway_of(request)
    return StreamingResponse(metrics_events(gateway), media_type="text/event-stream")


def _decision(config: ProviderConfig, eligible: set[str]) -> dict[str, Any]:
    """Explain why one provider is or is not a routing candidate."""
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("disabled")
    if config.enabled and config.id not in eligible:
        reasons.append("time-window or health")
    return {
        "provider_id": config.id,
        "model": config.model,
        "eligible": config.id in eligible,
        "reasons": reasons,
    }


def simulate_body(gateway: Gateway, model: str, prompt: str) -> dict[str, Any]:
    """Explain the routing decision for a candidate request without calling upstreams."""
    now = datetime.now(timezone.utc)
    rankings = rank_candidates(
        gateway.providers, gateway.health.states(), gateway.config.routing, now.hour, now.isoweekday()
    )
    eligible = {item.provider_id for item in rankings}
    return {
        "model": model,
        "prompt_length": len(prompt),
        "ranking": [item.__dict__ for item in rankings],
        "decisions": [_decision(config, eligible) for config in gateway.providers],
    }


@router.post("/simulate")
async def simulate(request: Request) -> dict[str, Any]:
    """Explain the routing decision for a candidate request without calling upstreams."""
    body = await read_json(request)
    return simulate_body(gateway_of(request), str(body.get("model", "")), str(body.get("prompt", "")))
