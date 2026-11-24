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
    _validate_unique_client_fields(keys)
    return keys


def _validate_unique_client_fields(keys: list[ClientKeyConfig]) -> None:
    ids = [key.id for key in keys]
    if len(ids) != len(set(ids)):
        raise ConfigError("client key ids must be distinct")
    env_names = [key.api_key_env for key in keys]
    if len(env_names) != len(set(env_names)):
        raise ConfigError("client keys must use distinct api_key_env values")
    if "PROXY_API_KEY" in env_names:
        raise ConfigError("a client key cannot use PROXY_API_KEY as its secret env")


def validate_provider_credentials_against_client_keys(
    keys: list[ClientKeyConfig], providers: list[ProviderConfig], env: Mapping[str, str]
) -> None:
    """Reject runtime provider credentials that alias a caller key."""
    client_values = {env.get(key.api_key_env, "") for key in keys}
    client_values.discard("")
    for provider in providers:
        value = provider.api_key(env)
        if value and value in client_values:
            raise ConfigError(f"provider {provider.id!r} credential aliases a client key")


def _reject_collision(active: list[str], values: set[str], message: str) -> None:
    if set(active) & values:
        raise ConfigError(message)


def _check_credential_collisions(
    active: list[str],
    proxy_api_key: str | None,
    admin_token: str | None,
    providers: list[ProviderConfig],
    env: Mapping[str, str],
) -> None:
    if len(active) != len(set(active)):
        raise ConfigError("client key env values must be distinct")
    reserved = {value for value in (proxy_api_key, admin_token) if value}
    _reject_collision(active, reserved, "a client key resolves to a reserved gateway credential")
    upstream = {value for provider in providers if (value := provider.api_key(env))}
    _reject_collision(active, upstream, "a client key resolves to an upstream provider credential")


def _require_usable_credential(
    keys: list[ClientKeyConfig],
    proxy_api_key: str | None,
    admin_token: str | None,
    active: list[str],
) -> None:
    if keys and not proxy_api_key and not active and not admin_token:
        raise ConfigError("no usable proxy credential or admin token is configured")


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
    _check_credential_collisions(active, proxy_api_key, admin_token, providers, env)
    _require_usable_credential(keys, proxy_api_key, admin_token, active)


def _proxy_auth_configured(
    proxy_api_key: str | None, client_keys: list[ClientKeyConfig], env: Mapping[str, str]
) -> bool:
    if proxy_api_key or not client_keys:
        return True
    return any(bool(env.get(key.api_key_env)) for key in client_keys)


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
        proxy_auth_configured=_proxy_auth_configured(proxy_api_key, client_keys, env),
    )


def load_app_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Load configuration from the file named by POLYGATE_CONFIG and the environment."""
    source = env if env is not None else os.environ
    config_path = source.get("POLYGATE_CONFIG")
    document: Mapping[str, Any] = _load_toml(Path(config_path)) if config_path else {}
    return build_app_config(document, source)
