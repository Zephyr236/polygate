"""FastAPI dependency helpers shared by API routers."""

from __future__ import annotations

from fastapi import Request

from polygate.gateway import Gateway


def gateway_of(request: Request) -> Gateway:
    """Return the live gateway from application state."""
    gateway: Gateway = request.app.state.gateway_holder["gateway"]
    return gateway
