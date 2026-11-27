"""Bearer-token authentication dependencies for admin and proxy surfaces."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

from polygate.api_keys import hash_api_key, policy_for_record
from polygate.config import ClientKeyConfig, ClientPolicy
from polygate.password import session_digest


def _bearer(request: Request) -> str:
    """Extract the bearer credential from the authorization header."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


def _legacy_admin(expected: str | None, provided: str) -> bool:
    return bool(expected and provided and secrets.compare_digest(provided, expected))


async def _session_admin(request: Request, provided: str) -> bool:
    if not provided:
        return False
    return bool(await request.app.state.store.admin_session_valid(session_digest(provided)))


async def require_admin(request: Request) -> None:
    """Accept a browser session or the legacy ADMIN_TOKEN on admin endpoints."""
    expected = request.app.state.config.admin_token
    provided = _bearer(request)
    if _legacy_admin(expected, provided) or await _session_admin(request, provided):
        return
    configured = await request.app.state.store.admin_password_configured()
    if not expected and not configured:
        raise HTTPException(status_code=503, detail="admin password is not configured")
    raise HTTPException(status_code=401, detail="invalid admin credentials")


def _active_clients(clients: list[tuple[ClientKeyConfig, str]]) -> list[tuple[ClientKeyConfig, str]]:
    return [(key, value) for key, value in clients if value]


def _matched_client(provided: str, active: list[tuple[ClientKeyConfig, str]]) -> ClientKeyConfig | None:
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


async def _generated_policy(request: Request, provided: str) -> ClientPolicy | None:
    if not provided:
        return None
    record = await request.app.state.store.api_key_policy(hash_api_key(provided))
    return None if record is None else policy_for_record(record)


def _open_policy(
    expected: str | None, clients: list[tuple[ClientKeyConfig, str]], generated: int
) -> ClientPolicy | None:
    return ClientPolicy("open") if not expected and not clients and generated == 0 else None


def _missing_credentials(
    expected: str | None, active: list[tuple[ClientKeyConfig, str]], generated: int
) -> bool:
    return not expected and not active and generated == 0


async def _configured_policy(request: Request, provided: str) -> ClientPolicy:
    expected = request.app.state.config.proxy_api_key
    clients: list[tuple[ClientKeyConfig, str]] = request.app.state.client_keys
    active = _active_clients(clients)
    generated = await request.app.state.store.api_key_count()
    open_policy = _open_policy(expected, clients, generated)
    if open_policy is not None:
        return open_policy
    if _missing_credentials(expected, active, generated):
        raise HTTPException(status_code=503, detail="no proxy api key is configured")
    policy = _match_policy(provided, expected, active)
    if policy is None:
        raise HTTPException(status_code=401, detail="invalid proxy api key")
    return policy


async def require_proxy_key(request: Request) -> ClientPolicy:
    """Resolve a generated key, legacy key or configured client key."""
    provided = _bearer(request) or request.headers.get("x-api-key", "")
    policy = await _generated_policy(request, provided)
    return policy if policy is not None else await _configured_policy(request, provided)


def _credential_matches(provided: str, expected: str) -> bool:
    """Compare the presented proxy credential in constant time."""
    return secrets.compare_digest(provided, expected)
