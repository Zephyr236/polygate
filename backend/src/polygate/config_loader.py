"""Configuration loading and validation for providers and caller keys."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from polygate.config import (
    AppConfig,
    ClientKeyConfig,
    ConfigError,
    ProviderConfig,
    RoutingConfig,
)

if sys.version_info >= (3, 11):  # pragma: no branch
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def _load_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file into a mapping, raising ConfigError on failure."""
    try:
        parsed: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
        return parsed
    except FileNotFoundError as error:
        raise ConfigError(f"config file not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from error


def parse_providers_document(document: Mapping[str, Any]) -> list[ProviderConfig]:
    """Validate a providers mapping into provider configs."""
    providers_raw = document.get("provider", [])
    if not isinstance(providers_raw, list):
        raise ConfigError("provider entries must be a list of tables")
    return [ProviderConfig.model_validate(item) for item in providers_raw]


def validate_client_keys_against_providers(
    keys: list[ClientKeyConfig], providers: list[ProviderConfig]
) -> None:
    """Require every client allowlist to reference the current provider pool."""
    known = {provider.id for provider in providers}
    for key in keys:
        unknown = set(key.allowed_providers) - known
        if unknown:
            raise ConfigError(f"client key {key.id!r} references unknown providers: {sorted(unknown)}")


def parse_client_keys(document: Mapping[str, Any], providers: list[ProviderConfig]) -> list[ClientKeyConfig]:
    """Validate caller keys and reject unknown provider allowlist entries."""
    raw = document.get("client_key", [])
    if not isinstance(raw, list):
        raise ConfigError("client_key entries must be a list of tables")
    keys = [ClientKeyConfig.model_validate(item) for item in raw]
    validate_client_keys_against_providers(keys, providers)
    env_names = [key.api_key_env for key in keys]
    if len(env_names) != len(set(env_names)):
        raise ConfigError("client keys must use distinct api_key_env values")
    if "PROXY_API_KEY" in env_names:
        raise ConfigError("a client key cannot use PROXY_API_KEY as its secret env")
    return keys


def validate_client_key_provisioning(
    keys: list[ClientKeyConfig],
    env: Mapping[str, str],
    proxy_api_key: str | None,
    admin_token: str | None,
    providers: list[ProviderConfig],
) -> None:
    """Reject ambiguous credentials and a fully unprovisioned client-key set."""
    values = [env.get(key.api_key_env, "") for key in keys]
    active = [value for value in values if value]
    if len(active) != len(set(active)):
        raise ConfigError("client key env values must be distinct")
    if proxy_api_key and any(value == proxy_api_key for value in active):
        raise ConfigError("a client key resolves to the legacy PROXY_API_KEY value")
    if admin_token and any(value == admin_token for value in active):
        raise ConfigError("a client key resolves to ADMIN_TOKEN")
    upstream = {provider.api_key(env) for provider in providers}
    if any(value in upstream for value in active):
        raise ConfigError("a client key resolves to an upstream provider credential")
    if keys and not proxy_api_key and not active:
        raise ConfigError("client keys are configured but no api_key_env is set")


def build_app_config(document: Mapping[str, Any], env: Mapping[str, str]) -> AppConfig:
    """Build the application config from a document and environment overrides."""
    providers_file = env.get("POLYGATE_PROVIDERS_FILE")
    providers = parse_providers_document(document)
    client_keys = parse_client_keys(document, providers)
    proxy_api_key = env.get("PROXY_API_KEY") or None
    admin_token = env.get("ADMIN_TOKEN") or None
    validate_client_key_provisioning(client_keys, env, proxy_api_key, admin_token, providers)
    routing_raw = document.get("routing", {})
    routing = RoutingConfig.model_validate(routing_raw) if routing_raw else RoutingConfig()
    return AppConfig(
        providers=providers,
        client_keys=client_keys,
        routing=routing,
        database_path=Path(env.get("POLYGATE_DATABASE", "data/polygate.db")),
        admin_token=admin_token,
        proxy_api_key=proxy_api_key,
        providers_file=Path(providers_file) if providers_file else None,
    )


def load_app_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Load configuration from the file named by POLYGATE_CONFIG and the environment."""
    source = env if env is not None else os.environ
    config_path = source.get("POLYGATE_CONFIG")
    document: Mapping[str, Any] = _load_toml(Path(config_path)) if config_path else {}
    return build_app_config(document, source)
