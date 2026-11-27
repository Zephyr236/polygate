"""Gherkin steps for caller-key contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from polygate.api_keys import policy_for_record
from polygate.config import ClientPolicy, ConfigError, ProviderConfig
from polygate.config_loader import build_app_config

FEATURE = Path(__file__).resolve().parents[3] / "specs" / "features" / "auth.feature"
scenarios(str(FEATURE))


@pytest.fixture()
def state() -> dict[str, Any]:
    return {"document": {"provider": []}, "env": {}}


def _provider(provider_id: str) -> dict[str, object]:
    return {"id": provider_id, "base_url": "https://x", "model": "m", "api_key_env": "K"}


@given(parsers.parse('a gateway with providers "{providers}"'))
def gateway_with_providers(state: dict[str, Any], providers: str) -> None:
    state["document"]["provider"] = [_provider(item) for item in providers.split('" and "')]


@given(parsers.parse('a client key "{key_id}" allowing only "{provider}"'))
def key_allowing(state: dict[str, Any], key_id: str, provider: str) -> None:
    state["document"]["client_key"] = [
        {"id": key_id, "api_key_env": "TEAM_A_KEY", "allowed_providers": [provider]}
    ]
    state["env"]["TEAM_A_KEY"] = "team-a-secret"


@given(parsers.parse('a gateway with an admin token "{token}"'))
def admin_token(state: dict[str, Any], token: str) -> None:
    state["document"]["provider"] = [_provider("a")]
    state["env"]["ADMIN_TOKEN"] = token


@given(parsers.parse('a client key whose resolved value is "{value}"'))
def key_value(state: dict[str, Any], value: str) -> None:
    state["document"]["client_key"] = [
        {"id": "team-a", "api_key_env": "TEAM_A_KEY", "allowed_providers": ["a"]}
    ]
    state["env"]["TEAM_A_KEY"] = value


@given("an unprovisioned optional client key")
def unprovisioned_key(state: dict[str, Any]) -> None:
    state["document"]["client_key"] = [{"id": "team-a", "api_key_env": "MISSING", "allowed_providers": ["a"]}]


@given(parsers.parse('a legacy proxy key "{value}"'))
def legacy_key(state: dict[str, Any], value: str) -> None:
    state["env"]["PROXY_API_KEY"] = value


@when("I build the gateway configuration")
def build_config(state: dict[str, Any]) -> None:
    try:
        state["config"] = build_app_config(state["document"], state["env"])
        state["error"] = None
    except ConfigError as error:
        state["config"] = None
        state["error"] = error


@when(parsers.parse('I evaluate the client policy for provider "{provider}"'))
def evaluate_policy(state: dict[str, Any], provider: str) -> None:
    key = state["document"]["client_key"][0]
    state["allowed"] = ClientPolicy(
        key_id=key["id"], allowed_providers=frozenset(key["allowed_providers"])
    ).allows(provider)


@then("the policy allows the provider")
def policy_allows(state: dict[str, Any]) -> None:
    assert state["allowed"] is True


@then("the policy rejects the provider")
def policy_rejects(state: dict[str, Any]) -> None:
    assert state["allowed"] is False


@then("configuration fails with a credential collision")
def collision(state: dict[str, Any]) -> None:
    assert state["error"] is not None
    assert "reserved gateway credential" in str(state["error"])


@then("configuration succeeds")
def succeeds(state: dict[str, Any]) -> None:
    assert state["error"] is None
    assert state["config"] is not None
    assert isinstance(state["config"].providers[0], ProviderConfig)


@then("configuration fails with no usable credential")
def unusable(state: dict[str, Any]) -> None:
    assert state["error"] is not None
    assert "no usable proxy credential" in str(state["error"])


@given(parsers.parse('a generated key record for tier "{tier}" allowing only "{provider}"'))
def generated_key_record(state: dict[str, Any], tier: str, provider: str) -> None:
    state["record"] = {"id": "key_test", "tier": tier, "allowed_providers": [provider]}


@when("I resolve the generated key policy")
def resolve_generated_policy(state: dict[str, Any]) -> None:
    state["policy"] = policy_for_record(state["record"])


@then(parsers.parse('the generated policy rejects provider "{provider}"'))
def generated_policy_rejects(state: dict[str, Any], provider: str) -> None:
    assert state["policy"].allows(provider) is False


@then("the generated policy uses economy weights")
def generated_policy_economy(state: dict[str, Any]) -> None:
    assert state["policy"].weights is not None
    assert state["policy"].weights.cost == 0.5
    assert state["policy"].respect_priority is False
