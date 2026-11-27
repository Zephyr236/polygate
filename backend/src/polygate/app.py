"""FastAPI application assembling proxy, admin, metrics and SPA routes."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from polygate.api import account, admin, api_keys, health
from polygate.api.proxy import router as proxy_router
from polygate.config import AppConfig
from polygate.config_loader import load_app_config
from polygate.gateway import Gateway, build_gateway
from polygate.storage import MetricsStore


def _lifespan_factory(
    app_config: AppConfig,
    store: MetricsStore,
    keys: dict[str, str],
    owned_client: httpx.AsyncClient | None,
    gateway_holder: dict[str, Gateway],
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build the lifespan handler that owns database and HTTP client lifetimes."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Manage database and HTTP client lifetimes around the app."""
        Path(app_config.database_path).parent.mkdir(parents=True, exist_ok=True)
        await store.open()
        http_client = owned_client or httpx.AsyncClient()
        gateway_holder["gateway"] = build_gateway(app_config, store, http_client, keys)
        try:
            yield
        finally:
            await store.close()
            if owned_client is None:
                await http_client.aclose()

    return lifespan


def _error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Render HTTP errors in the unified error envelope."""
    status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    detail = exc.detail if isinstance(exc, StarletteHTTPException) else "internal error"
    return JSONResponse({"error": {"message": detail, "status": status}}, status_code=status)


def create_app(
    config_env: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the ASGI application with lifespan-managed resources."""
    env = config_env if config_env is not None else dict(os.environ)
    app_config = load_app_config(env)
    static_dir = _static_dir(env, static_dir)
    store = MetricsStore(str(app_config.database_path))
    gateway_holder: dict[str, Gateway] = {}
    lifespan = _lifespan_factory(app_config, store, dict(env), client, gateway_holder)
    app = FastAPI(title="polygate", version="0.1.0", lifespan=lifespan)
    app.state.config = app_config
    app.state.client_keys = [(key, env.get(key.api_key_env, "")) for key in app_config.client_keys]
    app.state.store = store
    app.state.owned_client = client
    app.state.gateway_holder = gateway_holder
    app.include_router(proxy_router)
    app.include_router(account.router)
    app.include_router(api_keys.router)
    app.include_router(admin.router)
    app.include_router(health.router)
    if static_dir is not None and static_dir.is_dir():
        register_spa(app, static_dir)
    app.add_exception_handler(StarletteHTTPException, _error_handler)
    return app


def _static_dir(env: dict[str, str], static_dir: Path | None) -> Path | None:
    """Resolve the SPA directory from the argument or the environment."""
    if static_dir is not None:
        return static_dir
    configured = env.get("POLYGATE_STATIC_DIR")
    return Path(configured) if configured else None


def register_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA with a fallback to index.html."""
    index = static_dir / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        """Serve static assets, falling back to index.html for SPA routes."""
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and static_dir.resolve() in candidate.parents:  # noqa: ASYNC240
            return FileResponse(candidate)
        return FileResponse(index)


from polygate.api.deps import gateway_of  # noqa: E402,F401
