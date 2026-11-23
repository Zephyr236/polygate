"""Bearer-token authentication dependencies for admin and proxy surfaces."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request


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


def require_proxy_key(request: Request) -> None:
    """Require the proxy API key when one is configured."""
    expected = request.app.state.config.proxy_api_key
    if not expected:
        return
    if not _proxy_credential_matches(request, expected):
        raise HTTPException(status_code=401, detail="invalid proxy api key")


def _proxy_credential_matches(request: Request, expected: str) -> bool:
    """Compare the presented proxy credential in constant time."""
    provided = _bearer(request) or request.headers.get("x-api-key", "")
    return secrets.compare_digest(provided, expected)
