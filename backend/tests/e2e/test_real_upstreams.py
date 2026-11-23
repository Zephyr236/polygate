"""Optional smoke test against the real upstream channels (real marker, manual runs)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from polygate.app import create_app

pytestmark = pytest.mark.real

SEED = """
[[provider]]
id = "amr"
base_url = "https://amr-link.open-design.ai/v1"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"
max_tokens_min = 3000
max_concurrency = 4
priority = 1

[provider.retry]
attempts = 1

[[provider]]
id = "zen"
base_url = "https://opencode.ai/zen/go/v1"
model = "deepseek-v4.1-flash"
api_key_env = "ZEN_API_KEY"
session_header = "x-opencode-session"
session_mode = "uuid-per-request"
max_concurrency = 4
priority = 2

[provider.retry]
attempts = 1

[[provider]]
id = "ok8888"
base_url = "https://8888ok.cc/v1"
model = "deepseek-v4.1-flash"
api_key_env = "OK8888_API_KEY"
max_concurrency = 2
lanes = 2
priority = 5
cost_coefficient = 0.15

[provider.retry]
attempts = 1

[provider.timeouts]
connect_seconds = 15
total_seconds = 180
"""


def _require(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        pytest.skip(f"{env_name} is not set")
    return value


@pytest.fixture()
def gateway() -> httpx.Client:
    _require("AMR_API_KEY")
    _require("ZEN_API_KEY")
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "providers.toml"
        config.write_text(SEED, encoding="utf-8")
        app = create_app(
            config_env={
                "POLYGATE_CONFIG": str(config),
                "POLYGATE_DATABASE": str(Path(tmp) / "real.db"),
                "ADMIN_TOKEN": "real-token",
                "AMR_API_KEY": os.environ.get("AMR_API_KEY", ""),
                "ZEN_API_KEY": os.environ.get("ZEN_API_KEY", ""),
                "OK8888_API_KEY": os.environ.get("OK8888_API_KEY", ""),
            }
        )
        with TestClient(app) as client:
            yield client  # type: ignore[misc]


def test_real_chat_completion(gateway: httpx.Client) -> None:
    """One non-streaming completion must return text through some channel."""
    payload = {
        "model": "deepseek-v4.1-flash",
        "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
        "max_tokens": 4000,
    }
    response = gateway.post("/v1/chat/completions", json=payload, timeout=200)
    assert response.status_code == 200, response.text[:400]
    assert "PONG" in response.json()["choices"][0]["message"]["content"]


def test_real_streaming_completion(gateway: httpx.Client) -> None:
    """Streaming must produce deltas and terminate cleanly."""
    payload = {
        "model": "deepseek-v4.1-flash",
        "messages": [{"role": "user", "content": "Count 1 to 3"}],
        "stream": True,
        "max_tokens": 4000,
    }
    with gateway.stream("POST", "/v1/chat/completions", json=payload, timeout=200) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "[DONE]" in body


def test_real_metrics_recorded(gateway: httpx.Client) -> None:
    """Calls made above must show up in the admin metrics endpoint."""
    metrics = gateway.get(
        "/admin/metrics?range=1h", headers={"authorization": "Bearer real-token"}, timeout=30
    )
    assert metrics.status_code == 200
    assert metrics.json()["overview"]["calls"] >= 1
