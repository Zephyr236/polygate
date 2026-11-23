"""Tests for protocol translation and SSE framing."""

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
    encode_openai_done,
    encode_openai_usage,
    iter_anthropic_deltas,
    iter_openai_deltas,
)


def _request(**overrides: object) -> InternalRequest:
    base: dict[str, object] = {
        "model": "m",
        "messages": (Message("user", "hi"),),
        "max_tokens": 100,
    }
    base.update(overrides)
    return InternalRequest(**base)  # type: ignore[arg-type]


def test_openai_upstream_payload_minimum_tokens_and_stream_options() -> None:
    payload = openai.to_upstream_payload(_request(max_tokens=10, stream=True), "up", 3000)
    assert payload["max_tokens"] == 3000
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    payload = openai.to_upstream_payload(_request(temperature=0.2), "up", 0)
    assert payload["temperature"] == 0.2
    assert "stream_options" not in payload


def test_openai_parse_response_and_usage() -> None:
    body = {
        "model": "up",
        "choices": [
            {
                "message": {"content": "PONG", "reasoning_content": "hmm"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 36,
            "completion_tokens": 18,
            "prompt_tokens_details": {"cached_tokens": 24},
            "completion_tokens_details": {"reasoning_tokens": 15},
        },
    }
    response = openai.parse_response(body, "p")
    assert response.text == "PONG"
    assert response.thinking == "hmm"
    assert response.usage.cache_read_tokens == 24
    assert response.usage.cache_hit
    assert response.finish_reason == "stop"


def test_openai_parse_response_defaults() -> None:
    response = openai.parse_response({}, "p")
    assert response.text == ""
    assert response.thinking == ""
    assert response.finish_reason == "stop"
    response = openai.parse_response({"choices": [{"message": {"content": None}}]}, "p")
    assert response.text == ""


def test_openai_build_response_body() -> None:
    response = InternalResponse("hi", "why", "up", "p", Usage(10, 5, 2, 3))
    body = openai.build_response_body(response)
    assert body["choices"][0]["message"]["reasoning_content"] == "why"
    assert body["usage"]["prompt_tokens_details"]["cached_tokens"] == 3
    assert body["object"] == "chat.completion"


def test_openai_parse_request_shapes() -> None:
    request = openai.parse_request(
        {
            "model": "m",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": [{"text": "part"}, {"text": "s"}]},
                {"role": "tool", "content": 7},
            ],
            "max_completion_tokens": 50,
            "stream": True,
            "user": "conv",
        }
    )
    assert request.messages[1].content == "parts"
    assert request.messages[2].content == ""
    assert request.max_tokens == 50
    assert request.conversation_id == "conv"


def test_anthropic_upstream_payload() -> None:
    payload = anthropic.to_upstream_payload(_request(max_tokens=5), "up", 3000)
    assert payload["max_tokens"] == 3000
    assert payload["messages"][0]["role"] == "user"


def test_anthropic_parse_response_with_thinking_and_cache() -> None:
    body = {
        "model": "up",
        "content": [
            {"type": "thinking", "thinking": "sec"},
            {"type": "text", "text": "PONG"},
        ],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 36,
            "output_tokens": 17,
            "cache_read_input_tokens": 20,
            "cache_creation": {"ephemeral_5m_input_tokens": 5, "ephemeral_1h_input_tokens": 6},
        },
    }
    response = anthropic.parse_response(body, "p")
    assert response.text == "PONG"
    assert response.thinking == "sec"
    assert response.usage.cache_write_tokens == 11
    assert response.usage.reasoning_tokens == 0


def test_anthropic_parse_response_empty() -> None:
    response = anthropic.parse_response({}, "p")
    assert response.text == ""
    assert response.finish_reason == "end_turn"


def test_anthropic_build_response_body() -> None:
    response = InternalResponse("PONG", "", "up", "p", Usage(10, 5, 0, 2))
    body = anthropic.build_response_body(response)
    assert body["content"] == [{"type": "text", "text": "PONG"}]
    assert body["usage"]["cache_read_input_tokens"] == 2
    assert body["stop_sequence"] is None


def test_anthropic_parse_request_metadata_and_blocks() -> None:
    request = anthropic.parse_request(
        {
            "model": "m",
            "max_tokens": 20,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "metadata": {"user_id": "conv"},
        }
    )
    assert request.messages[0].content == "hi"
    assert request.conversation_id == "conv"


def test_openai_sse_frames() -> None:
    chunk = encode_openai_chunk("Hi", "up", "p")
    assert chunk.startswith("data: ")
    payload = json.loads(chunk[6:])
    assert payload["choices"][0]["delta"]["content"] == "Hi"
    done = encode_openai_chunk("", "up", "p", done=True)
    assert json.loads(done[6:])["choices"][0]["finish_reason"] == "stop"
    usage = encode_openai_usage({"total_tokens": 5}, "up", "p")
    assert json.loads(usage[6:])["choices"] == []
    assert encode_openai_done() == "data: [DONE]\n\n"


def test_anthropic_sse_frames() -> None:
    start = encode_anthropic_start("up", "p")
    assert start.startswith("event: message_start\ndata: ")
    assert json.loads(start.split("data: ")[1])["message"]["model"] == "up"
    assert "content_block_start" in encode_anthropic_block_start()
    delta = encode_anthropic_delta("Hi")
    assert json.loads(delta.split("data: ")[1])["delta"]["text"] == "Hi"
    stop = encode_anthropic_stop(10, 4)
    assert stop.count("event:") == 3
    assert '"output_tokens": 4' in stop


def test_iter_openai_deltas_extracts_text_and_usage() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"a"}}]}',
        'data: {"choices":[{"delta":{"content":""}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":9}}',
        "data: [DONE]",
        "event: ping",
    ]
    events = list(iter_openai_deltas(lines))
    assert events[0] == ("a", None)
    assert events[-1][1] == {"prompt_tokens": 9}


def test_iter_anthropic_deltas_extracts_text_and_usage() -> None:
    lines = [
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"a"}}',
        'data: {"type":"content_block_delta","delta":{"text":""}}',
        'data: {"type":"message_delta","usage":{"input_tokens":2,"output_tokens":1}}',
        "data: ",
        'data: {"type":"message_start"}',
    ]
    events = list(iter_anthropic_deltas(lines))
    assert events[0] == ("a", None)
    assert events[-1][1] == {"input_tokens": 2, "output_tokens": 1}
