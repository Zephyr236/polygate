"""Configuration models and loading for polygate providers and routing."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Protocol(str, Enum):
    """Upstream wire protocol spoken by a provider."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AuthStyle(str, Enum):
    """Credential placement for upstream authentication."""

    BEARER = "bearer"
    X_API_KEY = "x-api-key"
    BOTH = "both"


class SessionMode(str, Enum):
    """How a provider's session header is produced."""

    NONE = "none"
    PER_REQUEST = "uuid-per-request"
    PER_LANE = "uuid-per-lane"


class StreamUsage(str, Enum):
    """Where the upstream reports token usage while streaming."""

    INCLUDE_USAGE = "include_usage"
    MESSAGE_DELTA = "message_delta"
    NONE = "none"


class TimeWindow(BaseModel):
    """A recurring UTC window with an optional cost multiplier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=24)
    multiplier: float = Field(default=1.0, gt=0)
    weekday_from: int = Field(default=1, ge=1, le=7)
    weekday_to: int = Field(default=7, ge=1, le=7)

    def contains(self, hour: int, weekday: int) -> bool:
        """Report whether an hour and ISO weekday fall inside the window."""
        if not self.weekday_from <= weekday <= self.weekday_to:
            return False
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        return hour >= self.start_hour or hour < self.end_hour


class RetryPolicy(BaseModel):
    """Retry behaviour for retryable upstream failures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempts: int = Field(default=2, ge=1, le=6)
    base_delay_ms: int = Field(default=150, ge=0, le=10_000)
    max_delay_ms: int = Field(default=800, ge=0, le=30_000)
    jitter: float = Field(default=0.2, ge=0, le=1)


class Timeouts(BaseModel):
    """Connect and total timeouts for one upstream call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connect_seconds: float = Field(default=10.0, gt=0, le=120)
    total_seconds: float = Field(default=120.0, gt=0, le=900)


class ErrorRule(BaseModel):
    """Map an upstream error payload to a normalized error class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    json_path: str | None = None
    match: str | None = None
    error_class: str = "server_error"
    retryable: bool = True

    @model_validator(mode="after")
    def _require_matcher(self) -> ErrorRule:
        """Require at least one matcher on an error rule."""
        if self.json_path is None and self.match is None:
            raise ValueError("error rule needs json_path or match")
        return self


class ProviderConfig(BaseModel):
    """One upstream channel with its routing and quirk settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    base_url: str = Field(min_length=1)
    protocol: Protocol = Protocol.OPENAI
    model: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    api_key_env: str = Field(min_length=1)

    auth_style: AuthStyle = AuthStyle.BEARER
    session_header: str | None = None
    session_mode: SessionMode = SessionMode.NONE
    lanes: int = Field(default=1, ge=1, le=64)
    max_concurrency: int = Field(default=8, ge=1, le=512)
    max_tokens_min: int = Field(default=0, ge=0)
    stream_usage: StreamUsage = StreamUsage.NONE
    error_rules: list[ErrorRule] = Field(default_factory=list)

    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    timeouts: Timeouts = Field(default_factory=Timeouts)

    active_windows: list[TimeWindow] = Field(default_factory=list)
    cost_coefficient: float = Field(default=1.0, gt=0, le=100)
    priority: int = Field(default=1, ge=0, le=100)
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)

    input_price_per_mtok: float = Field(default=0.0, ge=0)
    output_price_per_mtok: float = Field(default=0.0, ge=0)

    def api_key(self, env: Mapping[str, str] | None = None) -> str | None:
        """Resolve the API key from the environment by variable name."""
        source = env if env is not None else os.environ
        value = source.get(self.api_key_env, "")
        return value or None

    def multiplier_at(self, hour: int, weekday: int) -> float:
        """Return the applicable cost multiplier for an hour and weekday."""
        for window in self.active_windows:
            if window.contains(hour, weekday):
                return window.multiplier
        return 1.0

    def is_active_at(self, hour: int, weekday: int) -> bool:
        """Report whether the provider may serve traffic in a time window."""
        if not self.active_windows:
            return True
        return any(window.contains(hour, weekday) for window in self.active_windows)


class RoutingWeights(BaseModel):
    """Relative weights of the routing score components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: float = Field(default=0.4, ge=0)
    speed: float = Field(default=0.25, ge=0)
    cost: float = Field(default=0.25, ge=0)
    cache: float = Field(default=0.1, ge=0)

    @model_validator(mode="after")
    def _non_zero(self) -> RoutingWeights:
        """Require a positive sum across routing weights."""
        if self.success + self.speed + self.cost + self.cache <= 0:
            raise ValueError("at least one routing weight must be positive")
        return self


class RoutingConfig(BaseModel):
    """Global routing, breaker and switch-over settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weights: RoutingWeights = Field(default_factory=RoutingWeights)
    exploration_ratio: float = Field(default=0.05, ge=0, le=1)
    max_switches: int = Field(default=3, ge=0, le=10)
    failure_threshold: int = Field(default=3, ge=1, le=20)
    cooldown_base_ms: int = Field(default=2_000, ge=100, le=120_000)
    cooldown_max_ms: int = Field(default=120_000, ge=100, le=3_600_000)
    half_open_probes: int = Field(default=1, ge=1, le=4)
    success_ema_alpha: float = Field(default=0.2, gt=0, le=1)
    latency_ema_alpha: float = Field(default=0.2, gt=0, le=1)
    speed_target_ms: float = Field(default=2_500.0, gt=0)


class ClientKeyConfig(BaseModel):
    """One caller key with a provider allowlist and optional routing weights."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(default="", max_length=120)
    api_key_env: str = Field(min_length=1)
    allowed_providers: list[str] = Field(min_length=1)
    weights: RoutingWeights | None = None
    respect_priority: bool = True


@dataclass(frozen=True)
class ClientPolicy:
    """Resolved caller policy used by authentication and routing."""

    key_id: str
    allowed_providers: frozenset[str] | None = None
    weights: RoutingWeights | None = None
    respect_priority: bool = True

    def allows(self, provider_id: str) -> bool:
        """Report whether the caller may use a provider."""
        return self.allowed_providers is None or provider_id in self.allowed_providers


@dataclass(frozen=True)
class AppConfig:
    """Runtime application settings aggregated from files and environment."""

    providers: list[ProviderConfig] = field(default_factory=list)
    client_keys: list[ClientKeyConfig] = field(default_factory=list)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    database_path: Path = Path("data/polygate.db")
    admin_token: str | None = None
    proxy_api_key: str | None = None
    providers_file: Path | None = None


class ConfigError(ValueError):
    """Raised when configuration input cannot be parsed or validated."""
