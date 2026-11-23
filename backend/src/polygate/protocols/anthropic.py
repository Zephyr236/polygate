"""Anthropic messages request and response translation."""

from __future__ import annotations

from typing import Any

from polygate.protocols.base import InternalRequest, InternalResponse, Message, Usage


def to_upstream_payload(request: InternalRequest, upstream_model: str, min_tokens: int) -> dict[str, Any]:
    """Build an Anthropic messages body for an upstream call."""
    payload: dict[str, Any] = {
        "model": upstream_model,
        "max_tokens": max(request.max_tokens, min_tokens),
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": request.stream,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    return payload


def parse_usage(payload: dict[str, Any]) -> Usage:
    """Extract token accounting from an Anthropic usage block."""
    raw = payload.get("usage") or {}
    cache_creation = raw.get("cache_creation") or {}
    return Usage(
        prompt_tokens=int(raw.get("input_tokens", 0)),
        completion_tokens=int(raw.get("output_tokens", 0)),
        reasoning_tokens=0,
        cache_read_tokens=int(raw.get("cache_read_input_tokens", 0)),
        cache_write_tokens=int(cache_creation.get("ephemeral_5m_input_tokens", 0))
        + int(cache_creation.get("ephemeral_1h_input_tokens", 0)),
    )


def _blocks_text(blocks: list[Any], kind: str, field: str) -> str:
    """Join the text of content blocks of one type."""
    return "".join(str(block.get(field, "")) for block in blocks if block.get("type") == kind)


def parse_response(payload: dict[str, Any], provider_id: str) -> InternalResponse:
    """Translate an Anthropic message body into the internal form."""
    blocks = payload.get("content") or []
    return InternalResponse(
        text=_blocks_text(blocks, "text", "text"),
        thinking=_blocks_text(blocks, "thinking", "thinking"),
        model=str(payload.get("model", "")),
        provider_id=provider_id,
        usage=parse_usage(payload),
        finish_reason=str(payload.get("stop_reason") or "end_turn"),
    )


def build_response_body(response: InternalResponse) -> dict[str, Any]:
    """Render an internal response as an Anthropic message body."""
    content: list[dict[str, Any]] = []
    if response.thinking:
        content.append({"type": "thinking", "thinking": response.thinking})
    content.append({"type": "text", "text": response.text})
    return {
        "id": f"msg_polygate_{response.provider_id}",
        "type": "message",
        "role": "assistant",
        "model": response.model,
        "content": content,
        "stop_reason": response.finish_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "cache_read_input_tokens": response.usage.cache_read_tokens,
            "cache_creation_input_tokens": response.usage.cache_write_tokens,
        },
    }


def parse_request(body: dict[str, Any]) -> InternalRequest:
    """Validate and normalize an incoming Anthropic messages request."""
    messages = tuple(
        Message(role=str(item.get("role", "user")), content=_text_content(item.get("content")))
        for item in body.get("messages", [])
    )
    return InternalRequest(
        model=str(body.get("model", "")),
        messages=messages,
        max_tokens=int(body.get("max_tokens") or 1024),
        temperature=body.get("temperature"),
        stream=bool(body.get("stream", False)),
        conversation_id=body.get("metadata", {}).get("user_id"),
    )


def _text_content(content: object) -> str:
    """Flatten string or block-list content into plain text."""
    if isinstance(content, str):
        return content
    return _join_blocks(content)


def _join_blocks(content: object) -> str:
    """Join text fields of block-list content."""
    blocks = content if isinstance(content, list) else []
    return "".join(str(item.get("text", "")) for item in blocks if isinstance(item, dict))
