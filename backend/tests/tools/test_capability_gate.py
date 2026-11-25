"""Tests for the workflow capability contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("capability_gate", REPO / "scripts" / "capability_gate.py")
assert SPEC and SPEC.loader
capability = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capability)


def test_checked_in_workflow_passes() -> None:
    assert capability.check(
        REPO / ".github" / "workflows" / "design-gate.yml", REPO / "specs" / "capabilities.yaml"
    ) == []


def test_write_capable_agent_is_rejected(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """
permissions:
  contents: read
jobs:
  design_gate:
    permissions:
      statuses: write
    steps:
      - run: python3 scripts/design_gate.py --no-publish
  publish:
    permissions:
      statuses: write
      issues: write
    steps:
      - run: python3 scripts/design_publish.py
"""
    )
    problems = capability.check(workflow, REPO / "specs" / "capabilities.yaml")
    assert any("agent job has forbidden permission" in problem for problem in problems)
