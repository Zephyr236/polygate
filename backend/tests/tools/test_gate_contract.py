"""Tests for the pure gate-contract policy."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("gate_contract", REPO / "scripts" / "gate_contract.py")
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def test_stale_head_is_not_reviewed() -> None:
    assert gate.resolve_review_target("h1", "h2") is None
    assert gate.resolve_review_target("h2", "h2") == "h2"


def test_superseded_status_is_skipped() -> None:
    statuses = [{"context": "design-review", "state": "success", "created_at": "2026-11-25T10:01:00Z"}]
    assert gate.is_superseded("2026-11-25T10:00:00Z", statuses) is True
    assert gate.is_superseded("2026-11-25T10:02:00Z", statuses) is False


def test_p0_blocks_p1_follows_up_p2_is_advisory() -> None:
    requirements = {
        "A": {"severity": "P0"},
        "B": {"severity": "P1"},
        "C": {"severity": "P2"},
    }
    report = {
        "verdict": "needs-changes",
        "findings": [
            {"title": "p0", "requirement_id": "A", "severity": "P0"},
            {"title": "p1", "requirement_id": "B", "severity": "P1"},
            {"title": "p2", "requirement_id": "C", "severity": "P2"},
        ],
    }
    decision = gate.decision_for_report(report, requirements)
    assert [item["decision"] for item in decision["decisions"]] == [
        "block",
        "follow-up",
        "advisory",
    ]


def test_failed_gate_blocks_a_forged_pass() -> None:
    decision = gate.decision_for_report({"verdict": "pass", "findings": []}, {}, gate_result="failure")
    assert decision["status"] == "block"


def test_insufficient_context_blocks() -> None:
    decision = gate.decision_for_report({"verdict": "insufficient-context", "findings": []}, {})
    assert decision["status"] == "block"
