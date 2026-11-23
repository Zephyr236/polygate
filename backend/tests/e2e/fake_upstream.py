"""Fake upstream providers reproducing the measured behaviour of each channel."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


@dataclass
class UpstreamBehaviour:
    """Scripted behaviour of one fake upstream provider."""

    concurrency_limit: int | None = None
    session_header: str | None = None
    latency_seconds: float = 0.0
    fail_first: int = 0
    error_status: int = 500
    error_body: dict[str, object] = field(default_factory=dict)
    stream_usage: str = "include_usage"
    require_auth: bool = True


@dataclass
class UpstreamCounters:
    """Live counters observed by the fake upstream."""

    inflight: int = 0
    peak: int = 0
    calls: int = 0
    rejected_by_concurrency: int = 0
    missing_session: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def build_upstream(behaviour: UpstreamBehaviour, counters: UpstreamCounters) -> FastAPI:
    """Create an ASGI app emulating one upstream provider."""
    app = FastAPI()
    state = {"failures_left": behaviour.fail_first}

    def enter() -> JSONResponse | None:
        with counters.lock:
            counters.calls += 1
            if state["failures_left"] > 0:
                state["failures_left"] -= 1
                return JSONResponse(behaviour.error_body, status_code=behaviour.error_status)
            if behaviour.concurrency_limit is not None and counters.inflight >= behaviour.concurrency_limit:
                counters.rejected_by_concurrency += 1
                return JSONResponse(
                    {
                        "error": {
                            "code": "tier_limit_exceeded",
                            "message": "membership concurrency limit exceeded",
                        }
                    },
                    status_code=400,
                )
            counters.inflight += 1
        return None

    def leave() -> None:
        with counters.lock:
            counters.inflight = max(counters.inflight - 1, 0)

    def check_session(request: Request) -> JSONResponse | None:
        if behaviour.session_header and not request.headers.get(behaviour.session_header):
            counters.missing_session += 1
            return JSONResponse(
                {"type": "error", "error": {"type": "MissingSessionID", "message": "missing session"}},
                status_code=400,
            )
        return None

    @app.post("/chat/completions", response_model=None)
    async def openai_chat(request: Request) -> Response:
        session_error = check_session(request)
        if session_error is not None:
            return session_error
        rejection = enter()
        if rejection is not None:
            return rejection
        body = await request.json()
        try:
            if body.get("stream"):
                return StreamingResponse(_openai_stream(behaviour), media_type="text/event-stream")
            if behaviour.latency_seconds:
                await asyncio.sleep(behaviour.latency_seconds)
            return JSONResponse(_openai_body())
        finally:
            if not body.get("stream"):
                leave()

    @app.post("/messages", response_model=None)
    async def anthropic_messages(request: Request) -> Response:
        session_error = check_session(request)
        if session_error is not None:
            return session_error
        rejection = enter()
        if rejection is not None:
            return rejection
        body = await request.json()
        try:
            if body.get("stream"):
                return StreamingResponse(_anthropic_stream(behaviour), media_type="text/event-stream")
            if behaviour.latency_seconds:
                await asyncio.sleep(behaviour.latency_seconds)
            return JSONResponse(_anthropic_body())
        finally:
            if not body.get("stream"):
                leave()

    @app.get("/models")
    async def models() -> JSONResponse:
        return JSONResponse({"data": [{"id": "deepseek-v4.1-flash"}]})

    return app


def _openai_body() -> dict[str, object]:
    return {
        "model": "deepseek-v4.1-flash",
        "choices": [{"message": {"content": "PONG"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 1},
        },
    }


def _anthropic_body() -> dict[str, object]:
    return {
        "model": "deepseek-v4.1-flash",
        "content": [{"type": "thinking", "thinking": "t"}, {"type": "text", "text": "PONG"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 3, "cache_read_input_tokens": 0},
    }


async def _openai_stream(behaviour: UpstreamBehaviour) -> object:
    yield 'data: {"choices":[{"delta":{"content":"PO"}}]}\n\n'
    yield 'data: {"choices":[{"delta":{"content":"NG"}}]}\n\n'
    yield 'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}\n\n'
    if behaviour.stream_usage == "include_usage":
        yield 'data: {"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":2}}\n\n'
    yield "data: [DONE]\n\n"


async def _anthropic_stream(behaviour: UpstreamBehaviour) -> object:
    yield 'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":9}}}\n\n'
    yield 'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"text":"PO"}}\n\n'
    yield ('event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"text":"NG"}}\n\n')
    if behaviour.stream_usage == "message_delta":
        yield (
            "event: message_delta\n"
            'data: {"type":"message_delta","usage":{"input_tokens":9,"output_tokens":2}}\n\n'
        )
    yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'


class ThreadedUpstream:
    """Run a fake upstream on a background thread for E2E tests."""

    def __init__(self, app: FastAPI) -> None:
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> ThreadedUpstream:
        self._thread.start()
        deadline = time.time() + 10
        while not self._server.started and time.time() < deadline:
            time.sleep(0.02)
        return self

    def __exit__(self, *_: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        sockets = getattr(self._server, "servers", [])
        for server in sockets:
            for socket in server.sockets:
                return f"http://127.0.0.1:{socket.getsockname()[1]}"
        raise RuntimeError("upstream did not start")


def serve(app: FastAPI) -> Iterator[str]:
    """Context helper yielding the base URL of a threaded upstream."""
    with ThreadedUpstream(app) as upstream:
        yield upstream.url


if __name__ == "__main__":  # pragma: no cover - manual helper
    behaviour = UpstreamBehaviour(concurrency_limit=10)
    counters = UpstreamCounters()
    app = build_upstream(behaviour, counters)
    uvicorn.run(app, host="127.0.0.1", port=9001, log_level="warning")


async def probe(url: str) -> int:
    """Call the fake upstream once and return the status code."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{url}/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
        )
        return response.status_code


def dump(payload: dict[str, object]) -> str:
    """Serialize a payload for log assertions."""
    return json.dumps(payload, sort_keys=True)
