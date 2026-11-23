"""Proxy endpoints exposing OpenAI and Anthropic compatible surfaces."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from polygate.api.auth import require_proxy_key
from polygate.api.bodies import read_json
from polygate.api.deps import gateway_of
from polygate.gateway import Gateway, record_route_result, record_stream_result
from polygate.protocols import anthropic, openai
from polygate.protocols.base import AllProvidersFailedError, InternalRequest, Usage
from polygate.protocols.sse import (
    encode_anthropic_block_start,
    encode_anthropic_delta,
    encode_anthropic_start,
    encode_anthropic_stop,
    encode_openai_chunk,
    encode_openai_done,
    encode_openai_usage,
)

router = APIRouter(tags=["proxy"])


class StreamState:
    """Track provider, usage and switching across streamed deltas."""

    def __init__(self) -> None:
        """Initialize an empty stream state."""
        self.provider_id = ""
        self.switched = 0
        self.started = False
        self.usage = Usage()

    def absorb(self, provider: str, usage: Usage | None) -> None:
        """Fold one routed delta into the accumulated state."""
        if provider != self.provider_id and self.provider_id:
            self.switched += 1
        self.provider_id = provider
        if usage is not None:
            self.usage = usage


def failure_response(error: AllProvidersFailedError) -> JSONResponse:
    """Render the aggregated provider failure as a JSON error."""
    return JSONResponse(
        {
            "error": {
                "message": "all provider candidates failed",
                "type": "providers_unavailable",
                "attempts": error.attempts,
            }
        },
        status_code=502,
    )


@router.post("/v1/chat/completions", dependencies=[Depends(require_proxy_key)], response_model=None)
async def chat_completions(request: Request) -> Response:
    """Serve OpenAI chat-completions requests through the router."""
    body = await read_json(request)
    gateway = gateway_of(request)
    internal = openai.parse_request(body)
    if internal.stream:
        return StreamingResponse(_openai_stream(gateway, internal), media_type="text/event-stream")
    try:
        route = await gateway.scheduler.complete(internal, gateway.keys)
    except AllProvidersFailedError as error:
        return failure_response(error)
    await record_route_result(gateway, internal, route)
    return JSONResponse(openai.build_response_body(route.result.response))


async def _openai_stream(gateway: Gateway, internal: InternalRequest) -> AsyncIterator[str]:
    """Stream OpenAI chunks while tracking provider and usage."""
    state = StreamState()
    try:
        async for text, usage, provider in gateway.scheduler.stream(internal, gateway.keys):
            state.absorb(provider, usage)
            if text:
                yield encode_openai_chunk(text, internal.model, provider)
    except AllProvidersFailedError:
        yield 'data: {"error": {"message": "all provider candidates failed"}}\n\n'
        return
    yield encode_openai_usage(openai.usage_body(state.usage), internal.model, state.provider_id)
    yield encode_openai_done()
    await record_stream_result(gateway, internal, state.provider_id, state.usage, state.switched, True)


@router.post("/v1/messages", dependencies=[Depends(require_proxy_key)], response_model=None)
async def messages(request: Request) -> Response:
    """Serve Anthropic messages requests through the router."""
    body = await read_json(request)
    gateway = gateway_of(request)
    internal = anthropic.parse_request(body)
    if internal.stream:
        return StreamingResponse(_anthropic_stream(gateway, internal), media_type="text/event-stream")
    try:
        route = await gateway.scheduler.complete(internal, gateway.keys)
    except AllProvidersFailedError as error:
        return failure_response(error)
    await record_route_result(gateway, internal, route)
    return JSONResponse(anthropic.build_response_body(route.result.response))


def _open_anthropic_frames(state: StreamState, model: str) -> list[str]:
    """Return the opening Anthropic frames once per stream."""
    if state.started:
        return []
    state.started = True
    return [encode_anthropic_start(model, state.provider_id), encode_anthropic_block_start()]


async def _anthropic_stream(gateway: Gateway, internal: InternalRequest) -> AsyncIterator[str]:
    """Stream Anthropic events while tracking provider and usage."""
    state = StreamState()
    try:
        async for text, usage, provider in gateway.scheduler.stream(internal, gateway.keys):
            state.absorb(provider, usage)
            if text:
                for frame in _open_anthropic_frames(state, internal.model):
                    yield frame
                yield encode_anthropic_delta(text)
    except AllProvidersFailedError:
        yield encode_anthropic_start(internal.model, "")
        yield 'event: error\ndata: {"type": "error", "error": {"type": "api_error"}}\n\n'
        return
    for frame in _open_anthropic_frames(state, internal.model):
        yield frame
    yield encode_anthropic_stop(state.usage.prompt_tokens, state.usage.completion_tokens)
    await record_stream_result(gateway, internal, state.provider_id, state.usage, state.switched, True)
