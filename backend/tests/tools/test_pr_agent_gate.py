"""Tests for the PR-Agent blocking gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "pr_agent_gate.py"
SPEC = importlib.util.spec_from_file_location("pr_agent_gate", SCRIPT)
assert SPEC and SPEC.loader
gate: ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _state(*, head: str = "abc", state: str = "ACTIVE", complete: bool = True) -> str:
    return (
        "<!-- pr-agent-review-state:v1\n"
        + json.dumps(
            {
                "findings": [{"path": "src/x.py", "line_start": 3, "body": "bad", "state": state}],
                "last_run": {"head_sha": head, "complete": complete},
            }
        )
        + "\n-->"
    )


def test_active_findings_blocks() -> None:
    findings = gate.evaluate([{"body": _state()}], "abc")
    assert len(findings) == 1


def test_resolved_findings_pass() -> None:
    assert gate.evaluate([{"body": _state(state="RESOLVED")}], "abc") == []


def test_missing_state_fails_closed() -> None:
    with pytest.raises(gate.GateError, match="no PR-Agent review state"):
        gate.evaluate([], "abc")


def test_incomplete_review_fails_closed() -> None:
    with pytest.raises(gate.GateError, match="incomplete"):
        gate.evaluate([{"body": _state(complete=False)}], "abc")


def test_wrong_head_is_ignored() -> None:
    with pytest.raises(gate.GateError, match="no PR-Agent review state"):
        gate.evaluate([{"body": _state(head="old")}], "abc")
