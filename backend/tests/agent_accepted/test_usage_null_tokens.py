"""Property test: usage parsers tolerate null and absent token fields.

An upstream may send a numeric usage field explicitly as ``null`` (it is a
common way to say "not reported").  ``dict.get(key, 0)`` returns ``None`` in
that case, so a bare ``int(...)`` raises ``TypeError`` and the whole response
is discarded.  These parsers must map null to zero instead.
"""

from __future__ import annotations

from hypothesis import example, given, settings, strategies as st

from polygate.protocols import anthropic, openai

_count = st.one_of(st.none(), st.integers(min_value=0, max_value=10**9))


def _expected(value: int | None) -> int:
    """A null or absent token field counts as zero."""
    return 0 if value is None else value


@settings(max_examples=50, deadline=None)
@given(prompt=_count, completion=_count, reasoning=_count, cached=_count)
@example(prompt=None, completion=None, reasoning=None, cached=None)
@example(prompt=7, completion=None, reasoning=None, cached=3)
def test_openai_usage_tolerates_null_token_fields(
    prompt: int | None, completion: int | None, reasoning: int | None, cached: int | None
) -> None:
    payload = {
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "prompt_tokens_details": {"cached_tokens": cached},
            "completion_tokens_details": {"reasoning_tokens": reasoning},
        }
    }
    usage = openai.parse_usage(payload)
    assert usage.prompt_tokens == _expected(prompt)
    assert usage.completion_tokens == _expected(completion)
    assert usage.reasoning_tokens == _expected(reasoning)
    assert usage.cache_read_tokens == _expected(cached)


@settings(max_examples=50, deadline=None)
@given(prompt=_count, completion=_count, cache_read=_count, cache_5m=_count, cache_1h=_count)
@example(prompt=None, completion=None, cache_read=None, cache_5m=None, cache_1h=None)
@example(prompt=8, completion=None, cache_read=5, cache_5m=None, cache_1h=2)
def test_anthropic_usage_tolerates_null_token_fields(
    prompt: int | None,
    completion: int | None,
    cache_read: int | None,
    cache_5m: int | None,
    cache_1h: int | None,
) -> None:
    payload = {
        "usage": {
            "input_tokens": prompt,
            "output_tokens": completion,
            "cache_read_input_tokens": cache_read,
            "cache_creation": {
                "ephemeral_5m_input_tokens": cache_5m,
                "ephemeral_1h_input_tokens": cache_1h,
            },
        }
    }
    usage = anthropic.parse_usage(payload)
    assert usage.prompt_tokens == _expected(prompt)
    assert usage.completion_tokens == _expected(completion)
    assert usage.cache_read_tokens == _expected(cache_read)
    assert usage.cache_write_tokens == _expected(cache_5m) + _expected(cache_1h)


def test_missing_usage_block_counts_as_zero() -> None:
    for module in (openai, anthropic):
        assert module.parse_usage({}).prompt_tokens == 0
        assert module.parse_usage({"usage": None}).completion_tokens == 0
