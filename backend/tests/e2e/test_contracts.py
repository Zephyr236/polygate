"""Contract tests: documented endpoints must never answer 5xx to typed input."""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest

pytest.importorskip("schemathesis", reason="schemathesis is only installed on Python 3.11+")

import schemathesis

from polygate.app import create_app

pytestmark = pytest.mark.contract


def _upstream(request: httpx.Request) -> httpx.Response:
    """Answer every upstream call so routing can succeed."""
    if request.url.path.endswith("/messages"):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "PONG"}]})
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "PONG"}}], "usage": {"prompt_tokens": 3}}
    )


def _build_app() -> object:
    tmp = tempfile.mkdtemp()
    return create_app(
        config_env={
            "ADMIN_TOKEN": "contract-token",
            "POLYGATE_DATABASE": str(Path(tmp) / "contract.db"),
            "AMR_API_KEY": "k1",
            "ZEN_API_KEY": "k2",
        },
        client=httpx.AsyncClient(transport=httpx.MockTransport(_upstream)),
    )


SCHEMA = schemathesis.openapi.from_asgi("/openapi.json", _build_app(), config=None)
CONFIG = schemathesis.Config(seed=0, max_failures=1, app="contract_app:app")
PROJECT = CONFIG.projects.default
PROJECT.base_url = "http://testserver"
PROJECT.headers = {"authorization": "Bearer contract-token"}
PROJECT.generation.max_examples = 15
SCHEMA.config = PROJECT


@SCHEMA.parametrize()
def test_no_server_errors(case: schemathesis.Case) -> None:
    """Fuzzed requests may be rejected, but never with a server error."""
    headers = dict(getattr(case, "headers", None) or {})
    headers["authorization"] = "Bearer contract-token"
    case.headers = headers  # type: ignore[attr-defined]
    response = case.call()  # type: ignore[attr-defined]
    if case.formatted_path.startswith("/readyz") and response.status_code == 503:
        return
    assert response.status_code < 500, f"{case.method} {case.formatted_path}: {response.status_code}"
