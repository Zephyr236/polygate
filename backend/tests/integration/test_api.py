"""ASGI-level tests for the public API surfaces using a scripted upstream transport."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from polygate.api.admin import metrics_events
from polygate.app import create_app
from polygate.config import ProviderConfig

AMR_KEY = "sk-test-amr"
ZEN_KEY = "oc-test-zen"

Handler = Callable[[httpx.Request], httpx.Response]


class Upstreams:
    """Scriptable set of upstream responses keyed by provider host."""

    def __init__(self) -> None:
        self.routes: dict[str, Handler] = {}

    def on(self, host: str, handler: Handler) -> None:
        self.routes[host] = handler

    def respond(self, payload: dict[str, object]) -> Handler:
        return lambda _: httpx.Response(200, json=payload)

    def error(self, status: int, payload: dict[str, object] | None = None) -> Handler:
        return lambda _: httpx.Response(status, json=payload or {})

    def stream(self, body: str) -> Handler:
        return lambda _: httpx.Response(200, text=body)

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            handler = self.routes.get(request.url.host)
            if handler is None:
                return httpx.Response(404, json={"error": {"message": "unscripted"}})
            return handler(request)

        return httpx.MockTransport(handle)


@pytest.fixture()
def upstreams() -> Upstreams:
    return Upstreams()


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "ADMIN_TOKEN": "admin-token",
        "PROXY_API_KEY": "",
        "POLYGATE_DATABASE": str(tmp_path / "test.db"),
        "AMR_API_KEY": AMR_KEY,
        "ZEN_API_KEY": ZEN_KEY,
    }


@contextlib.contextmanager
def _seeded(app: object) -> Iterator[TestClient]:
    with TestClient(app) as test_client:  # type: ignore[arg-type]
        gateway = test_client.app.state.gateway_holder["gateway"]
        providers = [
            ProviderConfig(
                id="amr",
                base_url="https://amr.example",
                model="deepseek-v4.1-flash-eco",
                api_key_env="AMR_API_KEY",
                max_tokens_min=3000,
            ),
            ProviderConfig(
                id="zen",
                base_url="https://zen.example/zen/go",
                model="deepseek-v4.1-flash",
                api_key_env="ZEN_API_KEY",
                protocol="anthropic",
                session_header="x-opencode-session",
                session_mode="uuid-per-request",
            ),
            ProviderConfig(
                id="ok8888",
                base_url="https://ok.example",
                model="deepseek-v4.1-flash",
                api_key_env="AMR_API_KEY",
            ),
        ]
        gateway.providers = providers
        gateway.health.replace(providers)
        gateway.scheduler.providers = providers
        yield test_client


@pytest.fixture()
def client(tmp_path: Path, upstreams: Upstreams) -> Iterator[TestClient]:
    app = create_app(config_env=_env(tmp_path), client=httpx.AsyncClient(transport=upstreams.transport()))
    with _seeded(app) as test_client:
        yield test_client


def test_healthz_and_readyz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["status"] == "ready"


def test_admin_requires_token(client: TestClient) -> None:
    assert client.get("/admin/providers").status_code == 401
    headers = {"authorization": "Bearer admin-token"}
    assert client.get("/admin/providers", headers=headers).status_code == 200


def test_chat_completions_routes_to_amr(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on(
        "amr.example", upstreams.respond({"model": "up", "choices": [{"message": {"content": "PONG"}}]})
    )
    response = client.post(
        "/v1/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "PONG"


def test_chat_completions_fails_over_to_zen(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("amr.example", upstreams.error(400, {"error": {"code": "tier_limit_exceeded"}}))
    upstreams.on("ok.example", upstreams.respond({"choices": [{"message": {"content": "ZEN"}}]}))
    response = client.post(
        "/v1/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "ZEN"


def test_chat_completions_all_fail(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("amr.example", upstreams.error(500, {"error": {"type": "server"}}))
    upstreams.on("zen.example", upstreams.error(503))
    response = client.post(
        "/v1/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 502
    assert response.json()["error"]["type"] == "providers_unavailable"


def test_chat_streaming_emits_sse(client: TestClient, upstreams: Upstreams) -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"PO"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )
    upstreams.on("amr.example", upstreams.stream(body))
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as response:
        assert response.status_code == 200
        joined = "\n".join(response.iter_lines())
    assert '"content": "PO"' in joined
    assert "[DONE]" in joined


def test_chat_streaming_all_fail_event(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("amr.example", upstreams.error(429, {"error": {"type": "rate_limit"}}))
    upstreams.on("zen.example", upstreams.error(401, {"error": {"type": "authentication_error"}}))
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as response:
        joined = "\n".join(response.iter_lines())
    assert "all provider candidates failed" in joined


def test_messages_endpoint_non_streaming(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("zen.example", upstreams.respond({"content": [{"type": "text", "text": "PONG"}]}))
    response = client.post("/v1/messages", json={"model": "m", "max_tokens": 10, "messages": []})
    assert response.status_code == 200
    assert response.json()["content"][0]["text"] == "PONG"


def test_messages_endpoint_streaming(client: TestClient, upstreams: Upstreams) -> None:
    body = (
        "event: content_block_delta\n"
        'data: {"type":"content_block_delta","delta":{"text":"OK"}}\n\n'
        "event: message_delta\n"
        'data: {"type":"message_delta","usage":{"input_tokens":3,"output_tokens":1}}\n\n'
    )
    upstreams.on("zen.example", upstreams.stream(body))
    with client.stream(
        "POST",
        "/v1/messages",
        json={"model": "m", "max_tokens": 10, "messages": [], "stream": True},
    ) as response:
        joined = "\n".join(response.iter_lines())
    assert "message_start" in joined
    assert "OK" in joined
    assert "message_stop" in joined


def test_messages_all_fail(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("amr.example", upstreams.error(500))
    upstreams.on("zen.example", upstreams.error(500))
    response = client.post("/v1/messages", json={"model": "m", "max_tokens": 10, "messages": []})
    assert response.status_code == 502


def test_messages_stream_all_fail(client: TestClient, upstreams: Upstreams) -> None:
    upstreams.on("amr.example", upstreams.error(500))
    upstreams.on("zen.example", upstreams.error(500))
    with client.stream(
        "POST", "/v1/messages", json={"model": "m", "max_tokens": 10, "messages": [], "stream": True}
    ) as response:
        joined = "\n".join(response.iter_lines())
    assert "api_error" in joined


def test_metrics_endpoint_after_calls(client: TestClient, upstreams: Upstreams) -> None:
    headers = {"authorization": "Bearer admin-token"}
    upstreams.on("amr.example", upstreams.respond({"choices": [{"message": {"content": "PONG"}}]}))
    client.post("/v1/chat/completions", json={"model": "m", "messages": []})
    response = client.get("/admin/metrics?range=1h", headers=headers)
    assert response.status_code == 200
    assert response.json()["overview"]["calls"] == 1
    assert response.json()["providers"][0]["provider_id"] == "amr"
    assert client.get("/admin/metrics?range=nope", headers=headers).status_code == 400


def test_admin_events(client: TestClient) -> None:
    headers = {"authorization": "Bearer admin-token"}
    assert client.get("/admin/events", headers=headers).status_code == 200


@pytest.mark.asyncio
async def test_metrics_stream_frames(tmp_path: Path) -> None:
    app = create_app(
        config_env=_env(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))),
    )
    with _seeded(app) as test_client:
        gateway = test_client.app.state.gateway_holder["gateway"]
        frame = await asyncio.wait_for(anext(metrics_events(gateway)), timeout=5)
    assert frame.startswith("data: ")
    assert '"health"' in frame


def test_admin_providers_update(client: TestClient) -> None:
    headers = {"authorization": "Bearer admin-token"}
    payload = {
        "providers": [{"id": "new", "base_url": "https://n", "model": "m", "api_key_env": "ZEN_API_KEY"}]
    }
    response = client.put("/admin/providers", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["providers"][0]["id"] == "new"
    assert response.json()["providers"][0]["api_key_configured"] is True
    assert client.put("/admin/providers", json={"providers": {"id": "x"}}, headers=headers).status_code == 400
    assert (
        client.put("/admin/providers", json={"providers": [{"id": "Bad"}]}, headers=headers).status_code
        == 400
    )


def test_admin_simulate(client: TestClient) -> None:
    headers = {"authorization": "Bearer admin-token"}
    response = client.post("/admin/simulate", json={"model": "m", "prompt": "hello"}, headers=headers)
    assert response.status_code == 200
    assert len(response.json()["ranking"]) == 3
    assert response.json()["decisions"][0]["eligible"] is True


def test_prometheus_output(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "polygate_provider_success_rate" in response.text


def test_spa_fallback(tmp_path: Path) -> None:
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html>polygate</html>", encoding="utf-8")
    (static / "asset.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(
        config_env=_env(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(404))),
        static_dir=static,
    )
    with TestClient(app) as test_client:
        assert "polygate" in test_client.get("/").text
        assert "polygate" in test_client.get("/dashboard").text
        assert test_client.get("/asset.js").text == "console.log(1)"


def test_admin_without_token_config(tmp_path: Path) -> None:
    app = create_app(
        config_env={"POLYGATE_DATABASE": str(tmp_path / "t.db")},
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(404))),
    )
    with TestClient(app) as test_client:
        response = test_client.get("/admin/providers")
    assert response.status_code == 503


def test_client_key_selects_provider_and_admin_lists_it(
    tmp_path: Path, upstreams: Upstreams
) -> None:
    config = tmp_path / "providers.toml"
    config.write_text(
        """
[[provider]]
id = "amr"
base_url = "https://amr.example"
model = "m"
api_key_env = "AMR_API_KEY"

[[client_key]]
id = "team-a"
name = "Team A"
api_key_env = "TEAM_A_KEY"
allowed_providers = ["amr"]

[client_key.weights]
success = 0.5
speed = 0.2
cost = 0.2
cache = 0.1
""",
        encoding="utf-8",
    )
    env = _env(tmp_path)
    env["POLYGATE_CONFIG"] = str(config)
    env["TEAM_A_KEY"] = "team-a-key"
    upstreams.on("amr.example", upstreams.respond({"choices": [{"message": {"content": "PONG"}}]}))
    app = create_app(config_env=env, client=httpx.AsyncClient(transport=upstreams.transport()))
    with _seeded(app) as test_client:
        ok = test_client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": []},
            headers={"authorization": "Bearer team-a-key"},
        )
        assert ok.status_code == 200
        assert test_client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": []},
            headers={"authorization": "Bearer wrong"},
        ).status_code == 401
        listed = test_client.get("/admin/clients", headers={"authorization": "Bearer admin-token"})
        assert listed.status_code == 200
        body = listed.json()
        assert body["clients"][0]["id"] == "team-a"
        assert body["clients"][0]["key_configured"] is True
        assert "team-a-key" not in listed.text


def test_proxy_key_required_when_configured(tmp_path: Path, upstreams: Upstreams) -> None:
    env = _env(tmp_path)
    env["PROXY_API_KEY"] = "proxy-key"
    upstreams.on("amr.example", upstreams.respond({"choices": [{"message": {"content": "PONG"}}]}))
    app = create_app(config_env=env, client=httpx.AsyncClient(transport=upstreams.transport()))
    with _seeded(app) as test_client:
        assert (
            test_client.post("/v1/chat/completions", json={"model": "m", "messages": []}).status_code == 401
        )
        ok = test_client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": []},
            headers={"authorization": "Bearer proxy-key"},
        )
        assert ok.status_code == 200
        alt = test_client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": []},
            headers={"x-api-key": "proxy-key"},
        )
        assert alt.status_code == 200
