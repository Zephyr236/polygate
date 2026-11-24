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


def _active_clients(clients: list[tuple[ClientKeyConfig, str]]) -> list[tuple[ClientKeyConfig, str]]:
    return [(key, value) for key, value in clients if value]


def _matched_client(
    provided: str, active: list[tuple[ClientKeyConfig, str]]
) -> ClientKeyConfig | None:
    for key, value in active:
        if _credential_matches(provided, value):
            return key
    return None


def _policy_for_client(key: ClientKeyConfig) -> ClientPolicy:
    allowed = frozenset(key.allowed_providers) if key.allowed_providers else None
    return ClientPolicy(key.id, allowed, key.weights, key.respect_priority)


def _match_policy(
    provided: str, expected: str | None, active: list[tuple[ClientKeyConfig, str]]
) -> ClientPolicy | None:
    if expected and _credential_matches(provided, expected):
        return ClientPolicy("legacy")
    key = _matched_client(provided, active)
    return None if key is None else _policy_for_client(key)


def _resolve_policy(
    expected: str | None,
    clients: list[tuple[ClientKeyConfig, str]],
    active: list[tuple[ClientKeyConfig, str]],
    provided: str,
) -> ClientPolicy | None:
    if not expected and not clients:
        return ClientPolicy("open")
    if not expected and not active:
        raise HTTPException(status_code=503, detail="no proxy api key is configured")
    return _match_policy(provided, expected, active)


def require_proxy_key(request: Request) -> ClientPolicy:
    """Resolve the caller policy from the legacy key or a configured client key."""
    expected = request.app.state.config.proxy_api_key
    clients: list[tuple[ClientKeyConfig, str]] = request.app.state.client_keys
    active = _active_clients(clients)
    provided = _bearer(request) or request.headers.get("x-api-key", "")
    policy = _resolve_policy(expected, clients, active, provided)
    if policy is None:
        raise HTTPException(status_code=401, detail="invalid proxy api key")
    return policy


def _credential_matches(provided: str, expected: str) -> bool:
    """Compare the presented proxy credential in constant time."""
    return secrets.compare_digest(provided, expected)
