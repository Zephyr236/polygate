"""Protocol-neutral request and response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Message:
    """A single conversation message."""

    role: str
    content: str


@dataclass(frozen=True)
class InternalRequest:
    """Normalized chat request accepted by the router."""

    model: str
    messages: tuple[Message, ...]
    max_tokens: int
    temperature: float | None = None
    stream: bool = False
    conversation_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    """Token accounting for one upstream call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def cache_hit(self) -> bool:
        """Report whether any prompt tokens were served from cache."""
        return self.cache_read_tokens > 0


@dataclass(frozen=True)
class InternalResponse:
    """Normalized non-streaming chat response."""

    text: str
    thinking: str
    model: str
    provider_id: str
    usage: Usage
    finish_reason: str = "stop"


class UpstreamError(Exception):
    """Normalized upstream failure with a classification."""

    def __init__(
        self,
        message: str,
        error_class: str = "server_error",
        status_code: int = 502,
        retryable: bool = True,
        retry_after_ms: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_class = error_class
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_ms = retry_after_ms


class AllProvidersFailedError(Exception):
    """Aggregated failure of every candidate provider."""

    def __init__(self, attempts: list[dict[str, object]]) -> None:
        super().__init__("all provider candidates failed")
        self.attempts = attempts
