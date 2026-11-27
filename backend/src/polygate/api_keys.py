"""Generated caller API keys and tier-based routing policies."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from polygate.config import ClientPolicy, RoutingWeights

TIER_WEIGHTS: dict[str, RoutingWeights] = {
    "premium": RoutingWeights(success=0.5, speed=0.3, cost=0.05, cache=0.15),
    "economy": RoutingWeights(success=0.3, speed=0.1, cost=0.5, cache=0.1),
}


@dataclass(frozen=True)
class GeneratedKey:
    """A newly generated key whose plaintext is returned only once."""

    id: str
    token: str
    prefix: str
    key_hash: str


def generate_api_key() -> GeneratedKey:
    """Create a high-entropy key and its non-reversible lookup digest."""
    token = "pg_" + secrets.token_urlsafe(32)
    return GeneratedKey(
        id="key_" + uuid.uuid4().hex,
        token=token,
        prefix=token[:12],
        key_hash=hash_api_key(token),
    )


def hash_api_key(token: str) -> str:
    """Hash a presented API key for database lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def policy_for_record(record: dict[str, Any]) -> ClientPolicy:
    """Map a generated key record to the scheduler policy."""
    tier = str(record.get("tier", "standard"))
    allowed = frozenset(str(item) for item in record.get("allowed_providers") or [])
    weights = TIER_WEIGHTS.get(tier)
    return ClientPolicy(
        key_id=f"api-key:{record['id']}",
        allowed_providers=allowed or None,
        weights=weights,
        respect_priority=tier != "economy",
    )
