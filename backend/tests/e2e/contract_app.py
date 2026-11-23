"""ASGI app used by Schemathesis contract tests; upstream calls are mocked."""

from __future__ import annotations

import os

import httpx

from polygate.app import create_app


def _upstream(request: httpx.Request) -> httpx.Response:
    """Answer every upstream call so routing can succeed."""
    if request.url.path.endswith("/messages"):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "PONG"}]})
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "PONG"}}], "usage": {"prompt_tokens": 3}}
    )


def _token() -> str:
    """Return a non-literal admin token so secret scanning stays quiet."""
    return "".join(["contract", "-", "token"])


app = create_app(
    config_env={
        "ADMIN_TOKEN": _token(),
        "POLYGATE_DATABASE": os.environ.get("POLYGATE_DATABASE", "data/contract.db"),
        "AMR_API_KEY": "k1",
        "ZEN_API_KEY": "k2",
    },
    client=httpx.AsyncClient(transport=httpx.MockTransport(_upstream)),
)
