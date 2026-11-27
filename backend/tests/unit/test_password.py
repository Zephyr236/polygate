"""Password hashing and session-token tests."""

from __future__ import annotations

import pytest

from polygate.password import (
    hash_password,
    new_session_token,
    session_digest,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    assert not verify_password("correct horse battery staple", "broken")


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        hash_password("short")


def test_session_tokens_are_random_and_hashed() -> None:
    first = new_session_token()
    second = new_session_token()
    assert first != second
    assert len(first) > 32
    assert len(session_digest(first)) == 64
    assert session_digest(first) != first
