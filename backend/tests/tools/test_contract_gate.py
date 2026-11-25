"""Tests for requirement, scenario and finding traceability."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("contract_gate", REPO / "scripts" / "contract_gate.py")
assert SPEC and SPEC.loader
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def test_complete_contract_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    (tmp_path / "specs" / "features" / "auth.feature").write_text(
        "@req:AUTH-001 @p0\nFeature: auth\n"
        "  Scenario: A key stays inside its allowlist\n    Given x\n    Then y\n"
    )
    (tmp_path / "specs" / "requirements.yaml").write_text(
        "requirements:\n  AUTH-001:\n    title: Auth\n    statement: stays inside\n"
        "    severity: P0\n    owner: security\n    verify: [specs/features/auth.feature]\n"
    )
    (tmp_path / "specs" / "scope.yaml").write_text("requirements: [AUTH-001]\n")
    (tmp_path / "bdd.xml").write_text(
        '<testsuites><testcase name="test_a_key_stays_inside_its_allowlist"/></testsuites>'
    )
    monkeypatch.chdir(tmp_path)
    assert contract.main(["contract_gate.py", "--junit", "bdd.xml"]) == 0


def test_missing_p0_scenario_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    (tmp_path / "specs" / "requirements.yaml").write_text(
        "requirements:\n  AUTH-001:\n    title: Auth\n    statement: stays inside\n"
        "    severity: P0\n    owner: security\n    verify: [specs/features]\n"
    )
    (tmp_path / "specs" / "scope.yaml").write_text("requirements: [AUTH-001]\n")
    monkeypatch.chdir(tmp_path)
    assert contract.main(["contract_gate.py"]) == 1


def test_p0_design_finding_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    (tmp_path / "specs" / "requirements.yaml").write_text(
        "requirements:\n  AUTH-001:\n    title: Auth\n    statement: stays inside\n"
        "    severity: P0\n    owner: security\n    verify: [specs/features]\n"
    )
    (tmp_path / "specs" / "scope.yaml").write_text("requirements: [AUTH-001]\n")
    (tmp_path / "report.json").write_text(
        json.dumps(
            {
                "verdict": "needs-changes",
                "findings": [{"title": "x", "requirement_id": "AUTH-001", "severity": "P0"}],
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    assert contract.main(["contract_gate.py", "--design-report", "report.json"]) == 1
