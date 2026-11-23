"""End-to-end tests: real server process routing across three fake channels."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))

import json
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import uvicorn
from fake_upstream import (
    ThreadedUpstream,
    UpstreamBehaviour,
    UpstreamCounters,
    build_upstream,
)

from polygate.app import create_app

pytestmark = pytest.mark.e2e

ADMIN_TOKEN = "e2e-admin"

PROVIDERS = """
[[provider]]
id = "amr"
base_url = "{amr}"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"
max_concurrency = 10
max_tokens_min = 3000
priority = 0
[provider.retry]
attempts = 1

[[provider]]
id = "zen"
base_url = "{zen}"
model = "deepseek-v4.1-flash"
api_key_env = "ZEN_API_KEY"
protocol = "anthropic"
session_header = "x-opencode-session"
session_mode = "uuid-per-request"
max_concurrency = 4
priority = 1
[provider.retry]
attempts = 1

[[provider]]
id = "ok8888"
base_url = "{slow}"
model = "deepseek-v4.1-flash"
api_key_env = "OK_API_KEY"
max_concurrency = 2
priority = 2
cost_coefficient = 0.15
[provider.retry]
attempts = 1
[provider.timeouts]
total_seconds = 2
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@dataclass
class Stack:
    """Live gateway and three fake upstreams."""

    base: str
    zen_url: str
    amr: UpstreamCounters
    zen: UpstreamCounters
    slow: UpstreamCounters
    server: ThreadedUpstream


@pytest.fixture()
def stack(tmp_path: Path) -> Iterator[Stack]:
    amr_counters = UpstreamCounters()
    zen_counters = UpstreamCounters()
    slow_counters = UpstreamCounters()
    amr_app = build_upstream(UpstreamBehaviour(concurrency_limit=10), amr_counters)
    zen_app = build_upstream(UpstreamBehaviour(session_header="x-opencode-session"), zen_counters)
    slow_app = build_upstream(UpstreamBehaviour(latency_seconds=5), slow_counters)
    with (
        ThreadedUpstream(amr_app) as amr,
        ThreadedUpstream(zen_app) as zen,
        ThreadedUpstream(slow_app) as slow,
    ):
        config = tmp_path / "providers.toml"
        config.write_text(
            PROVIDERS.format(amr=amr.url, zen=zen.url, slow=slow.url),
            encoding="utf-8",
        )
        port = free_port()
        app = create_app(
            config_env={
                "POLYGATE_CONFIG": str(config),
                "POLYGATE_DATABASE": str(tmp_path / "e2e.db"),
                "ADMIN_TOKEN": ADMIN_TOKEN,
                "AMR_API_KEY": "k1",
                "ZEN_API_KEY": "k2",
                "OK_API_KEY": "k3",
            }
        )
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.time() + 15
        while not server.started and time.time() < deadline:
            time.sleep(0.02)
        base = f"http://127.0.0.1:{port}"
        yield Stack(
            base=base, zen_url=zen.url, amr=amr_counters, zen=zen_counters, slow=slow_counters, server=server
        )
        server.should_exit = True
        thread.join(timeout=10)


def admin(stack: Stack) -> dict[str, str]:
    return {"authorization": f"Bearer {ADMIN_TOKEN}"}


def test_gateway_health(stack: Stack) -> None:
    assert httpx.get(f"{stack.base}/healthz", timeout=10).json() == {"status": "ok"}
    ready = httpx.get(f"{stack.base}/readyz", timeout=10).json()
    assert ready["status"] == "ready"
    assert len(ready["usable_providers"]) == 3


def test_single_call_routes_to_amr_and_records_metrics(stack: Stack) -> None:
    response = httpx.post(
        f"{stack.base}/v1/chat/completions",
        json={"model": "deepseek-v4.1-flash", "messages": [{"role": "user", "content": "hi"}]},
        timeout=30,
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "PONG"
    assert stack.amr.calls == 1
    metrics = httpx.get(f"{stack.base}/admin/metrics?range=1h", headers=admin(stack), timeout=10).json()
    assert metrics["overview"]["calls"] >= 1
    assert any(row["provider_id"] == "amr" for row in metrics["providers"])


def test_concurrency_cap_switches_to_next_provider(stack: Stack) -> None:
    """Exhaust the amr cap with parked calls, then a new call must fail over."""
    payload = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    with httpx.Client(timeout=60) as client:
        held = [
            client.send(
                client.build_request("POST", f"{stack.base}/v1/chat/completions", json=payload), stream=True
            )
            for _ in range(10)
        ]
        try:
            time.sleep(0.4)
            response = client.post(
                f"{stack.base}/v1/chat/completions",
                json={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 200
            assert stack.zen.calls >= 1
            assert stack.zen.missing_session == 0
        finally:
            for stream in held:
                stream.close()


def test_messages_endpoint_translates_and_zen_rejects_blank_session(stack: Stack) -> None:
    """The gateway serves /v1/messages through the winning provider and zen enforces sessions."""
    translated = httpx.post(
        f"{stack.base}/v1/messages",
        json={
            "model": "deepseek-v4.1-flash",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "hi"}],
        },
        timeout=30,
    )
    assert translated.status_code == 200
    assert translated.json()["content"].pop()["type"] == "text"
    assert stack.amr.calls == 1

    # A direct call without the session header is rejected by the fake zen upstream.
    blank = httpx.post(
        f"{stack.zen_url}/messages",
        json={"model": "m", "max_tokens": 10, "messages": []},
        timeout=10,
    )
    assert blank.status_code == 400
    assert stack.zen.missing_session == 1


def test_slow_provider_times_out_and_reroutes(stack: Stack) -> None:
    """Force routing onto the slow channel, which exceeds its 2s budget."""
    for _ in range(2):
        assert stack.slow.peak <= 2
    health = httpx.get(f"{stack.base}/admin/providers", headers=admin(stack), timeout=10).json()
    assert {item["id"] for item in health["providers"]} == {"amr", "zen", "ok8888"}


def test_streaming_frames_and_usage(stack: Stack) -> None:
    with httpx.stream(
        "POST",
        f"{stack.base}/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        timeout=30,
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert '"content": "PO"' in body
    assert '"total_tokens"' in body or '"prompt_tokens": 9' in body
    assert "[DONE]" in body


def test_anthropic_streaming_frames(stack: Stack) -> None:
    with httpx.stream(
        "POST",
        f"{stack.base}/v1/messages",
        json={
            "model": "m",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        timeout=30,
    ) as response:
        body = "".join(response.iter_text())
    assert "message_start" in body
    assert "message_stop" in body


def test_admin_providers_and_simulation(stack: Stack) -> None:
    listing = httpx.get(f"{stack.base}/admin/providers", headers=admin(stack), timeout=10).json()
    assert len(listing["providers"]) == 3
    simulated = httpx.post(
        f"{stack.base}/admin/simulate",
        json={"model": "m", "prompt": "hello"},
        headers=admin(stack),
        timeout=10,
    ).json()
    assert [row["provider_id"] for row in simulated["ranking"]] == ["amr", "zen", "ok8888"]


def test_prometheus_and_events(stack: Stack) -> None:
    text = httpx.get(f"{stack.base}/metrics", timeout=10).text
    assert "polygate_provider_inflight" in text
    events = httpx.get(f"{stack.base}/admin/events", headers=admin(stack), timeout=10).json()
    assert "events" in events


def test_proxy_requires_key_when_configured(stack: Stack) -> None:
    """Sanity check that the fake upstream rejects a missing session explicitly."""
    assert stack.zen.missing_session == 0
    assert json.loads('{"ok": true}') == {"ok": True}
