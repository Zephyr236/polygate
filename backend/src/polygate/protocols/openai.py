"""OpenAI chat-completions request and response translation."""

from __future__ import annotations

from typing import Any

from polygate.protocols.base import InternalRequest, InternalResponse, Message, Usage


def to_upstream_payload(request: InternalRequest, upstream_model: str, min_tokens: int) -> dict[str, Any]:
    """Build an OpenAI chat-completions body for an upstream call."""
    payload: dict[str, Any] = {
        "model": upstream_model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "max_tokens": max(request.max_tokens, min_tokens),
        "stream": request.stream,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def parse_usage(payload: dict[str, Any]) -> Usage:
    """Extract token accounting from an OpenAI usage block."""
    raw = payload.get("usage") or {}
    details = raw.get("prompt_tokens_details") or {}
    completion_details = raw.get("completion_tokens_details") or {}
    return Usage(
        prompt_tokens=int(raw.get("prompt_tokens", 0)),
        completion_tokens=int(raw.get("completion_tokens", 0)),
        reasoning_tokens=int(completion_details.get("reasoning_tokens", 0)),
        cache_read_tokens=int(details.get("cached_tokens", 0)),
    )


def _as_text(value: object) -> str:
    """Return the value when it is a string, else an empty string."""
    return value if isinstance(value, str) else ""


def parse_response(payload: dict[str, Any], provider_id: str) -> InternalResponse:
    """Translate an OpenAI chat-completions body into the internal form."""
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return InternalResponse(
        text=_as_text(message.get("content")),
        thinking=_as_text(message.get("reasoning_content")),
        model=str(payload.get("model", "")),
        provider_id=provider_id,
        usage=parse_usage(payload),
        finish_reason=str(choice.get("finish_reason") or "stop"),
    )


def build_response_body(response: InternalResponse) -> dict[str, Any]:
    """Render an internal response as an OpenAI chat-completions body."""
    message: dict[str, Any] = {"role": "assistant", "content": response.text}
    if response.thinking:
        message["reasoning_content"] = response.thinking
    return {
        "id": f"polygate-{response.provider_id}",
        "object": "chat.completion",
        "model": response.model,
        "choices": [{"index": 0, "message": message, "finish_reason": response.finish_reason}],
        "usage": usage_body(response.usage),
    }


def usage_body(usage: Usage) -> dict[str, Any]:
    """Render token accounting in OpenAI naming."""
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.prompt_tokens + usage.completion_tokens,
        "prompt_tokens_details": {"cached_tokens": usage.cache_read_tokens},
        "completion_tokens_details": {"reasoning_tokens": usage.reasoning_tokens},
    }


def parse_request(body: dict[str, Any]) -> InternalRequest:
    """Validate and normalize an incoming OpenAI chat request."""
    messages = tuple(
        Message(role=str(item.get("role", "user")), content=_text_content(item.get("content")))
        for item in body.get("messages", [])
    )
    return InternalRequest(
        model=str(body.get("model", "")),
        messages=messages,
        max_tokens=int(body.get("max_tokens") or body.get("max_completion_tokens") or 1024),
        temperature=body.get("temperature"),
        stream=bool(body.get("stream", False)),
        conversation_id=body.get("user"),
    )


def _text_content(content: object) -> str:
    """Flatten string or block-list message content into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "".join(str(part) for part in parts)
    return ""
