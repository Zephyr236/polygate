"""Generated API key and tier policy tests."""

from __future__ import annotations

from polygate.api_keys import generate_api_key, hash_api_key, policy_for_record


def test_generated_key_is_random_and_hashed() -> None:
    first = generate_api_key()
    second = generate_api_key()
    assert first.token.startswith("pg_")
    assert first.token != second.token
    assert first.prefix == first.token[:12]
    assert first.key_hash == hash_api_key(first.token)
    assert first.key_hash != first.token


def test_tiers_change_scheduler_weights_and_priority() -> None:
    premium = policy_for_record({"id": "p", "tier": "premium", "allowed_providers": ["zen"]})
    economy = policy_for_record({"id": "e", "tier": "economy", "allowed_providers": ["zen"]})
    assert premium.allowed_providers == frozenset({"zen"})
    assert premium.weights is not None and premium.weights.cost == 0.05
    assert economy.weights is not None and economy.weights.cost == 0.5
    assert premium.respect_priority is True
    assert economy.respect_priority is False
