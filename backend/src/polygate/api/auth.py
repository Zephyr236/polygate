"""Bearer-token authentication dependencies for admin and proxy surfaces."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

from polygate.config import ClientKeyConfig, ClientPolicy


def _bearer(request: Request) -> str:
    """Extract the bearer credential from the authorization header."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


def require_admin(request: Request) -> None:
    """Require the configured admin token on admin endpoints."""
    expected = request.app.state.config.admin_token
    provided = _bearer(request)
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")


def require_proxy_key(request: Request) -> ClientPolicy:
    """Resolve the caller policy from the legacy key or a configured client key."""
    expected = request.app.state.config.proxy_api_key
    clients: list[tuple[ClientKeyConfig, str]] = request.app.state.client_keys
    active = [(key, value) for key, value in clients if value]
    if not expected and not clients:
        return ClientPolicy("open")
    if not expected and not active:
        raise HTTPException(status_code=503, detail="no proxy api key is configured")
    provided = _bearer(request) or request.headers.get("x-api-key", "")
    if expected and _credential_matches(provided, expected):
        return ClientPolicy("legacy")
    for key, value in active:
        if _credential_matches(provided, value):
            allowed = frozenset(key.allowed_providers) if key.allowed_providers else None
            return ClientPolicy(key.id, allowed, key.weights, key.respect_priority)
    raise HTTPException(status_code=401, detail="invalid proxy api key")


def _credential_matches(provided: str, expected: str) -> bool:
    """Compare the presented proxy credential in constant time."""
    return secrets.compare_digest(provided, expected)
