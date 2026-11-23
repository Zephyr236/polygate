"""Tests for the agent-gate decision policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_gate.policy import PolicyError, ensure_inside, load_policy

REPO = Path(__file__).resolve().parents[3]
POLICY = REPO / "agent" / "policy.toml"


def test_policy_loads_and_covers_every_artifact() -> None:
    policy = load_policy(POLICY)
    assert policy.version == 1
    assert policy.max_candidates >= 1
    referenced = {artifact for artifacts in policy.gaps.values() for artifact in artifacts}
    assert referenced == set(policy.artifacts)
    assert policy.decide("business_invariant", "e2e_test").oracle == "pre_post"
    assert policy.decide("internal_design", "adr_proposal").acceptance == "human"


def test_policy_rejects_unknown_gap_and_artifact() -> None:
    policy = load_policy(POLICY)
    with pytest.raises(PolicyError, match="unknown gap type"):
        policy.decide("made_up", "e2e_test")
    with pytest.raises(PolicyError, match="not allowed"):
        policy.decide("internal_design", "e2e_test")
    with pytest.raises(PolicyError, match="unknown artifact"):
        policy.decide("static_pattern", "made_up")


def test_missing_fields_reports_empty_values() -> None:
    policy = load_policy(POLICY)
    missing = policy.missing_fields("e2e_test", {"test_file": "x", "invariant": "", "pre_fix_commit": []})
    assert missing == ["invariant", "pre_fix_commit", "post_fix_commit", "incident_ref"]


def test_invalid_policy_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "policy.toml"
    path.write_text(
        '[artifacts.bad]\nacceptance = "maybe"\noracle = "none"\npaths = ["x/"]\nrequires = ["a"]\n',
        encoding="utf-8",
    )
    with pytest.raises(PolicyError, match="invalid acceptance"):
        load_policy(path)
    path.write_text('[gap_types.g]\nartifacts = ["missing"]\n', encoding="utf-8")
    with pytest.raises(PolicyError, match="unknown artifacts"):
        load_policy(path)
    with pytest.raises(PolicyError, match="not found"):
        load_policy(tmp_path / "absent.toml")


def test_ensure_inside_accepts_and_rejects_paths(tmp_path: Path) -> None:
    allowed = tmp_path / "rules" / "candidates"
    allowed.mkdir(parents=True)
    assert ensure_inside(tmp_path, "rules/candidates/x.yml", ("rules/candidates/",)) == allowed / "x.yml"
    with pytest.raises(PolicyError, match="absolute"):
        ensure_inside(tmp_path, "/etc/passwd", ("rules/candidates/",))
    with pytest.raises(PolicyError, match="outside"):
        ensure_inside(tmp_path, "backend/src/x.py", ("rules/candidates/",))
    with pytest.raises(PolicyError, match="escapes"):
        ensure_inside(tmp_path, "../../x.yml", ("rules/candidates/",))
