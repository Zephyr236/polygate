"""Server-sent-events encoding and decoding for both wire protocols."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping


def encode_openai_chunk(text_delta: str, model: str, provider_id: str, done: bool = False) -> str:
    """Render one OpenAI SSE chunk carrying a text delta."""
    delta = {"content": "" if done else text_delta}
    chunk = {
        "id": f"polygate-{provider_id}",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": "stop" if done else None}],
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def encode_openai_usage(usage_payload: dict[str, object], model: str, provider_id: str) -> str:
    """Render the OpenAI usage chunk that closes a stream."""
    chunk = {
        "id": f"polygate-{provider_id}",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [],
        "usage": usage_payload,
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def encode_openai_done() -> str:
    """Render the OpenAI stream terminator."""
    return "data: [DONE]\n\n"


def encode_anthropic_start(model: str, provider_id: str) -> str:
    """Render the Anthropic message_start event."""
    payload = {
        "type": "message_start",
        "message": {
            "id": f"msg_polygate_{provider_id}",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }
    return _anthropic_event("message_start", payload)


def encode_anthropic_block_start() -> str:
    """Render the Anthropic content_block_start event."""
    payload = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    return _anthropic_event("content_block_start", payload)


def encode_anthropic_delta(text_delta: str) -> str:
    """Render the Anthropic content_block_delta event."""
    payload = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text_delta},
    }
    return _anthropic_event("content_block_delta", payload)


def encode_anthropic_stop(input_tokens: int, output_tokens: int) -> str:
    """Render the closing contrast of message_delta and message_stop events."""
    delta = {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    block_stop = {"type": "content_block_stop", "index": 0}
    stop = {"type": "message_stop"}
    return (
        _anthropic_event("content_block_stop", block_stop)
        + _anthropic_event("message_delta", delta)
        + _anthropic_event("message_stop", stop)
    )


def _anthropic_event(name: str, payload: Mapping[str, object]) -> str:
    """Render one Anthropic named SSE event."""
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _openai_event(body: str) -> tuple[str, dict[str, object] | None] | None:
    chunk = json.loads(body)
    choices = chunk.get("choices") or []
    return _usage_event(chunk) if not choices else _delta_event(choices[0])


def _usage_event(chunk: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    usage = chunk.get("usage")
    return ("", usage) if isinstance(usage, dict) else None


def _delta_event(choice: dict[str, object]) -> tuple[str, None] | None:
    delta = choice.get("delta")
    text = delta.get("content") if isinstance(delta, dict) else None
    return (text, None) if isinstance(text, str) and text else None


def _frame_body(line: str) -> str:
    """Return the payload of a data line, or an empty string for non-data lines."""
    return line[5:].strip() if line.startswith("data:") else ""


def iter_openai_deltas(lines: Iterable[str]) -> Iterator[tuple[str, dict[str, object] | None]]:
    """Yield text deltas and the final usage block from OpenAI SSE lines."""
    for line in lines:
        body = _frame_body(line)
        if not body or body == "[DONE]":
            continue
        event = _openai_event(body)
        if event is not None:
            yield event


def _anthropic_event_parts(body: str) -> tuple[str, dict[str, object] | None] | None:
    event = json.loads(body)
    kind = event.get("type")
    return _anthropic_delta(event) if kind == "content_block_delta" else _anthropic_usage(event)


def _anthropic_delta(event: dict[str, object]) -> tuple[str, None] | None:
    delta = event.get("delta")
    text = delta.get("text") if isinstance(delta, dict) else None
    return (text, None) if isinstance(text, str) and text else None


def _anthropic_usage(event: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    usage = event.get("usage")
    return ("", usage) if event.get("type") == "message_delta" and isinstance(usage, dict) else None


def iter_anthropic_deltas(lines: Iterable[str]) -> Iterator[tuple[str, dict[str, object] | None]]:
    """Yield text deltas and the final usage block from Anthropic SSE lines."""
    for line in lines:
        body = line[5:].strip() if line.startswith("data:") else ""
        if not body:
            continue
        event = _anthropic_event_parts(body)
        if event is not None:
            yield event
