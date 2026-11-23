"""Generate the configuration reference page from the pydantic models."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))

from polygate.config import (  # noqa: E402
    AppConfig,
    ErrorRule,
    ProviderConfig,
    RetryPolicy,
    RoutingConfig,
    RoutingWeights,
    Timeouts,
    TimeWindow,
)

OUTPUT = ROOT / "docs" / "config-reference.md"

DESCRIPTIONS: dict[str, str] = {
    "id": "stable channel identifier, lowercase with dashes",
    "base_url": "upstream base URL without the protocol suffix",
    "protocol": "wire protocol the upstream speaks",
    "model": "upstream model name sent with each request",
    "aliases": "client-facing model aliases",
    "api_key_env": "environment variable holding the API key",
    "auth_style": "which credential header to send",
    "session_header": "header carrying a session id",
    "session_mode": "how session ids are generated",
    "lanes": "parallel session buckets",
    "max_concurrency": "concurrency slots per lane",
    "max_tokens_min": "floor applied to the request max_tokens",
    "stream_usage": "where the upstream reports usage while streaming",
    "error_rules": "rules mapping payloads or text onto error classes",
    "retry": "retry policy for retryable failures",
    "timeouts": "connect and total timeouts",
    "active_windows": "UTC windows restricting traffic with an optional multiplier",
    "cost_coefficient": "user-defined relative price weight",
    "priority": "lower values are tried first",
    "enabled": "whether the channel participates in routing",
    "tags": "free-form labels shown in the dashboard",
    "input_price_per_mtok": "USD per million prompt tokens",
    "output_price_per_mtok": "USD per million completion tokens",
    "weights": "relative weights of the routing score components",
    "exploration_ratio": "share of requests that may try a lower priority tier",
    "max_switches": "maximum provider switches per request",
    "failure_threshold": "consecutive failures that open a circuit",
    "cooldown_base_ms": "first cooldown duration",
    "cooldown_max_ms": "cooldown cap",
    "half_open_probes": "probes allowed while half open",
    "success_ema_alpha": "smoothing factor for success rate",
    "latency_ema_alpha": "smoothing factor for latency",
    "speed_target_ms": "latency that scores a perfect speed value",
    "attempts": "retry attempts per provider",
    "base_delay_ms": "first retry delay",
    "max_delay_ms": "retry delay cap",
    "jitter": "multiplicative jitter applied to delays",
    "connect_seconds": "connect timeout",
    "total_seconds": "total request timeout",
    "start_hour": "window start hour in UTC",
    "end_hour": "window end hour in UTC",
    "multiplier": "cost multiplier applied inside the window",
    "weekday_from": "first ISO weekday the window applies to",
    "weekday_to": "last ISO weekday the window applies to",
    "json_path": "dotted JSON path that must be present",
    "match": "case-insensitive text fragment that must appear",
    "error_class": "normalized error class",
    "retryable": "whether the error consumes retry budget",
    "success": "weight of the success rate component",
    "speed": "weight of the latency component",
    "cost": "weight of the inverse cost component",
    "cache": "weight of the cache hit component",
    "providers": "channel configurations loaded from the seed file",
    "database_path": "SQLite file for metrics, events and provider overrides",
    "admin_token": "bearer token protecting the admin API and UI",
    "proxy_api_key": "optional bearer token protecting /v1/*",
    "providers_file": "path of the provider seed file when set",
}

MODELS = [
    ProviderConfig,
    RetryPolicy,
    Timeouts,
    TimeWindow,
    ErrorRule,
    RoutingConfig,
    RoutingWeights,
]


def _fields(model: type) -> list[str]:
    """Return pydantic field names or dataclass field names."""
    if hasattr(model, "model_fields"):
        return list(model.model_fields)
    return [field.name for field in dataclasses.fields(model)]


def render() -> str:
    """Render the reference page as markdown."""
    lines = [
        "# Configuration reference",
        "",
        "Generated from the pydantic models in `backend/src/polygate/config.py`",
        "by `scripts/gen_config_reference.py`. Run the script after changing the models.",
        "",
    ]
    for model in MODELS:
        lines += [f"## {model.__name__}", "", "| Field | Description |", "| --- | --- |"]
        for name in _fields(model):
            lines.append(f"| `{name}` | {DESCRIPTIONS.get(name, 'see the model definition')} |")
        lines.append("")
    lines += ["## AppConfig (dataclass)", "", "| Field | Description |", "| --- | --- |"]
    for name in _fields(AppConfig):
        lines.append(f"| `{name}` | {DESCRIPTIONS.get(name, 'see the dataclass definition')} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write the generated page and report the target path."""
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
