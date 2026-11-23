"""Exact-payload assertions that pin protocol translation and SSE framing."""

from __future__ import annotations

import json

from polygate.protocols import anthropic, openai
from polygate.protocols.base import InternalRequest, InternalResponse, Message, Usage
from polygate.protocols.sse import (
    encode_anthropic_block_start,
    encode_anthropic_delta,
    encode_anthropic_start,
    encode_anthropic_stop,
    encode_openai_chunk,
    encode_openai_usage,
    iter_anthropic_deltas,
    iter_openai_deltas,
)


def _sse_payload(frame: str) -> dict[str, object]:
    return json.loads(frame.split("data: ", 1)[1])


def test_openai_chunk_exact_payload() -> None:
    frame = encode_openai_chunk("ab", "model-x", "provider-1")
    body = _sse_payload(frame)
    assert body == {
        "id": "polygate-provider-1",
        "object": "chat.completion.chunk",
        "model": "model-x",
        "choices": [{"index": 0, "delta": {"content": "ab"}, "finish_reason": None}],
    }
    final = _sse_payload(encode_openai_chunk("ignored", "model-x", "p", done=True))
    assert final["choices"][0]["delta"]["content"] == ""
    assert final["choices"][0]["finish_reason"] == "stop"


def test_openai_usage_chunk_exact_payload() -> None:
    body = _sse_payload(encode_openai_usage({"prompt_tokens": 3}, "m", "p"))
    assert body["object"] == "chat.completion.chunk"
    assert body["choices"] == []
    assert body["usage"] == {"prompt_tokens": 3}
    assert body["id"] == "polygate-p"


def test_anthropic_start_exact_payload() -> None:
    frame = encode_anthropic_start("m", "p")
    name, payload = frame.split("\n", 1)
    assert name == "event: message_start"
    body = json.loads(payload.split("data: ", 1)[1])
    assert body == {
        "type": "message_start",
        "message": {
            "id": "msg_polygate_p",
            "type": "message",
            "role": "assistant",
            "model": "m",
            "content": [],
            "stop_reason": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }


def test_anthropic_block_and_delta_exact_payload() -> None:
    block = _sse_payload(encode_anthropic_block_start())
    assert block == {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    delta = _sse_payload(encode_anthropic_delta("hi"))
    assert delta == {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}}


def test_anthropic_stop_exact_events() -> None:
    events = [event for event in encode_anthropic_stop(11, 3).split("\n\n") if event]
    names = [event.split("\n", 1)[0] for event in events]
    assert names == [
        "event: content_block_stop",
        "event: message_delta",
        "event: message_stop",
    ]
    assert json.loads(events[0].split("data: ", 1)[1]) == {"type": "content_block_stop", "index": 0}
    delta = json.loads(events[1].split("data: ", 1)[1])
    assert delta == {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"input_tokens": 11, "output_tokens": 3},
    }
    assert json.loads(events[2].split("data: ", 1)[1]) == {"type": "message_stop"}


def test_openai_usage_body_numeric_fields() -> None:
    body = openai.usage_body(Usage(10, 4, 2, 3))
    assert body == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "prompt_tokens_details": {"cached_tokens": 3},
        "completion_tokens_details": {"reasoning_tokens": 2},
    }


def test_openai_build_response_body_exact() -> None:
    body = openai.build_response_body(InternalResponse("PONG", "", "up", "p", Usage(6, 2)))
    assert body["id"] == "polygate-p"
    assert body["model"] == "up"
    assert body["choices"] == [
        {"index": 0, "message": {"role": "assistant", "content": "PONG"}, "finish_reason": "stop"}
    ]
    assert body["usage"]["total_tokens"] == 8


def test_anthropic_build_response_body_exact() -> None:
    body = anthropic.build_response_body(InternalResponse("PONG", "why", "up", "p", Usage(6, 2, 0, 3, 4)))
    assert body["id"] == "msg_polygate_p"
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["content"] == [
        {"type": "thinking", "thinking": "why"},
        {"type": "text", "text": "PONG"},
    ]
    assert body["stop_reason"] == "stop"
    assert body["usage"] == {
        "input_tokens": 6,
        "output_tokens": 2,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": 4,
    }


def test_parse_usage_exact_counts() -> None:
    usage = openai.parse_usage(
        {
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "completion_tokens_details": {"reasoning_tokens": 1},
            }
        }
    )
    assert usage.prompt_tokens == 7
    assert usage.completion_tokens == 3
    assert usage.reasoning_tokens == 1
    assert usage.cache_read_tokens == 0
    usage = anthropic.parse_usage(
        {
            "usage": {
                "input_tokens": 8,
                "output_tokens": 2,
                "cache_read_input_tokens": 5,
                "cache_creation": {"ephemeral_5m_input_tokens": 1, "ephemeral_1h_input_tokens": 2},
            }
        }
    )
    assert usage.prompt_tokens == 8
    assert usage.cache_read_tokens == 5
    assert usage.cache_write_tokens == 3


def test_upstream_payload_exact_shapes() -> None:
    request = InternalRequest("m", (Message("system", "s"), Message("user", "u")), 40, temperature=0.3)
    payload = openai.to_upstream_payload(request, "up", 0)
    assert payload == {
        "model": "up",
        "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        "max_tokens": 40,
        "stream": False,
        "temperature": 0.3,
    }
    payload = anthropic.to_upstream_payload(request, "up", 3000)
    assert payload["max_tokens"] == 3000
    assert payload["model"] == "up"
    assert payload["stream"] is False


def test_parse_request_exact_roles_and_limits() -> None:
    request = openai.parse_request(
        {"model": "m", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 9, "temperature": 0.0}
    )
    assert request.model == "m"
    assert request.messages == (Message("user", "hi"),)
    assert request.max_tokens == 9
    assert request.temperature == 0.0
    request = anthropic.parse_request(
        {
            "model": "m",
            "messages": [{"role": "assistant", "content": "hi"}],
            "max_tokens": 9,
            "temperature": 0.2,
        }
    )
    assert request.messages[0].role == "assistant"
    assert request.temperature == 0.2


def test_parse_request_defaults() -> None:
    request = openai.parse_request({"model": "m"})
    assert request.messages == ()
    assert request.max_tokens == 1024
    assert request.stream is False
    request = anthropic.parse_request({"model": "m", "messages": []})
    assert request.max_tokens == 1024


def test_parse_response_exact_text_selection() -> None:
    response = openai.parse_response(
        {
            "model": "up",
            "choices": [
                {
                    "message": {"content": "PONG", "reasoning_content": "why"},
                    "finish_reason": "length",
                }
            ],
        },
        "p",
    )
    assert response.model == "up"
    assert response.finish_reason == "length"
    assert response.provider_id == "p"
    response = anthropic.parse_response(
        {"model": "up", "content": [{"type": "text", "text": "B"}], "stop_reason": "max_tokens"},
        "p",
    )
    assert response.finish_reason == "max_tokens"
    assert response.provider_id == "p"


def test_iter_delta_edge_cases() -> None:
    text_event = 'data: {"choices":[{"delta":{"content":5}}]}'
    assert list(iter_openai_deltas([text_event])) == []
    assert list(iter_openai_deltas(['data: {"choices":[]}'])) == []
    assert list(iter_anthropic_deltas(['data: {"type":"message_stop"}'])) == []
    assert list(iter_anthropic_deltas(['data: {"type":"content_block_delta","delta":{"text":1}}'])) == []
