"""Fine-grained assertions for upstream error classification helpers."""

from __future__ import annotations

import httpx

from polygate.config import ErrorRule, ProviderConfig
from polygate.providers.base import (
    _error_body_text,
    _error_type,
    _lookup_path,
    _retry_after_ms,
    _rule_match,
    _status_for,
    classify_by_rule,
    classify_error,
    status_to_class,
)


def _config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {"id": "p", "base_url": "https://x", "model": "m", "api_key_env": "K"}
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def test_error_type_reads_nested_type_only() -> None:
    assert _error_type({"error": {"type": "rate_limit"}}) == "rate_limit"
    assert _error_type({"error": "plain"}) == ""
    assert _error_type({}) == ""


def test_error_body_text_json_and_plain() -> None:
    text, payload = _error_body_text(httpx.Response(500, json={"code": "X"}))
    assert payload == {"code": "X"}
    assert '"code"' in text
    text, payload = _error_body_text(httpx.Response(500, text="raw failure"))
    assert payload == {}
    assert text == "raw failure"


def test_lookup_path_nested_and_missing() -> None:
    assert _lookup_path({"a": {"b": {"c": "v"}}}, "a.b.c") == "v"
    assert _lookup_path({"a": {"b": {"c": 5}}}, "a.b.c") == "5"
    assert _lookup_path({"a": 1}, "a.b") == ""
    assert _lookup_path({}, "x") == ""


def test_rule_match_variants() -> None:
    path_rule = ErrorRule(json_path="error.code")
    assert _rule_match(path_rule, "text", {"error": {"code": "tier"}})
    assert not _rule_match(path_rule, "text", {"error": {}})
    text_rule = ErrorRule(match="Bad Thing")
    assert _rule_match(text_rule, "postgres bad thing", {})
    assert _rule_match(text_rule, "BAD THING", {})
    assert not _rule_match(text_rule, "other", {})
    bare = ErrorRule(json_path="a", match="x")
    assert _rule_match(bare, "no match", {"a": 1})


def test_status_to_class_branches() -> None:
    assert status_to_class(429, "") == "rate_limited"
    assert status_to_class(400, "rate_limit_error") == "rate_limited"
    assert status_to_class(401, "") == "auth_error"
    assert status_to_class(403, "") == "auth_error"
    assert status_to_class(404, "") == "model_not_found"
    assert status_to_class(503, "") == "server_error"
    assert status_to_class(418, "") == "client_error"


def test_status_for_overrides_and_passthrough() -> None:
    assert _status_for("concurrency_limited", 400) == 429
    assert _status_for("auth_error", 500) == 401
    assert _status_for("model_not_found", 500) == 404
    assert _status_for("client_error", 500) == 400
    assert _status_for("timeout", 0) == 504
    assert _status_for("transport_error", 0) == 503
    assert _status_for("unknown", 403) == 403
    assert _status_for("unknown", 200) == 502


def test_retry_after_header_parsing() -> None:
    assert _retry_after_ms(httpx.Response(429, headers={"retry-after": "2"})) == 2000
    assert _retry_after_ms(httpx.Response(429, headers={"retry-after": "0.5"})) == 500
    assert _retry_after_ms(httpx.Response(429, headers={"retry-after": "soon"})) is None
    assert _retry_after_ms(httpx.Response(429)) is None


def test_classify_by_rule_returns_first_match_with_status() -> None:
    config = _config(error_rules=[ErrorRule(match="bad", error_class="auth_error", retryable=False)])
    error = classify_by_rule(config, "very Bad request", {"x": 1}, 400)
    assert error is not None
    assert error.error_class == "auth_error"
    assert error.status_code == 401
    assert not error.retryable
    assert classify_by_rule(config, "fine", {}, 400) is None


def test_classify_error_retryable_flags_and_retry_after() -> None:
    error = classify_error(_config(), httpx.Response(429, headers={"retry-after": "3"}, json={}))
    assert error.error_class == "rate_limited"
    assert error.retryable
    assert error.retry_after_ms == 3000
    error = classify_error(_config(), httpx.Response(503, json={"error": {"type": "x"}}))
    assert error.error_class == "server_error"
    assert error.retryable
    assert error.status_code == 502
    error = classify_error(_config(), httpx.Response(401, json={}))
    assert not error.retryable


def test_error_body_text_caps_length() -> None:
    text, _ = _error_body_text(httpx.Response(500, text="x" * 900))
    assert len(text) == 500
    text, _ = _error_body_text(httpx.Response(500, json={"k": "y" * 900}))
    assert len(text) <= 500
