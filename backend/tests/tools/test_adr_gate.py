"""Tests for the MADR/requirement ADR gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("adr_gate", REPO / "scripts" / "adr_gate.py")
assert SPEC and SPEC.loader
adr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adr)


def test_checked_in_adrs_pass() -> None:
    assert adr.check(REPO / "docs" / "adr", REPO / "specs" / "requirements.yaml") == []


def test_unknown_requirement_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "0001-test.md").write_text(
        "# ADR\n\n- Status: Accepted\n- Requirements: NOPE-001\n\n"
        "## Context\nx\n## Decision\ny\n## Consequences\nz\n"
    )
    requirements = tmp_path / "requirements.yaml"
    requirements.write_text("requirements:\n  AUTH-001:\n    severity: P0\n")
    assert any("unknown requirement" in problem for problem in adr.check(tmp_path, requirements))
