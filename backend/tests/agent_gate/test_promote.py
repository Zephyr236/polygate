"""Tests for promoting accepted candidates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from agent_gate.promote import PromoteError, promote

REPO = Path(__file__).resolve().parents[3]
POLICY = REPO / "agent" / "policy.toml"


def _candidate(repo: Path, meta: dict[str, object]) -> Path:
    path = repo / "agent" / "candidates" / str(meta["id"]) / "candidate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


def _report(repo: Path, gap: str, artifact: str, verdict: str = "pass") -> Path:
    path = repo / "report.json"
    path.write_text(json.dumps({"verdict": verdict, "gap_type": gap, "artifact": artifact}), encoding="utf-8")
    return path


def _rule_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    (tmp_path / "rules" / "candidates").mkdir(parents=True)
    (tmp_path / "rules" / "promoted.yml").write_text("rules: []\n", encoding="utf-8")
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "accepted.json").write_text("[]\n", encoding="utf-8")
    rule = tmp_path / "rules" / "candidates" / "candidate.yml"
    rule.write_text(
        "rules:\n  - id: promoted-probe\n    languages: [python]\n    severity: ERROR\n"
        "    message: probe\n    pattern: print(...)\n",
        encoding="utf-8",
    )
    meta = {
        "id": "candidate-promote",
        "gap_type": "static_pattern",
        "artifact": "semgrep_rule",
        "summary": "probe",
        "rule_file": "rules/candidates/candidate.yml",
        "positive_fixture": "agent/fixtures/bad",
        "negative_fixture": "agent/fixtures/good",
        "incident_ref": "docs/incidents.md#probe",
    }
    return _candidate(tmp_path, meta), rule, _report(tmp_path, "static_pattern", "semgrep_rule")


def test_promote_semgrep_rule_appends_and_registers(tmp_path: Path) -> None:
    candidate, rule, report = _rule_repo(tmp_path)
    entry = promote(candidate, report, tmp_path, "https://example/issue/1", POLICY)
    promoted = yaml.safe_load((tmp_path / "rules" / "promoted.yml").read_text(encoding="utf-8"))
    assert [item["id"] for item in promoted["rules"]] == ["promoted-probe"]
    assert not rule.exists()
    assert entry["target"] == "rules/promoted.yml"
    registry = json.loads((tmp_path / "agent" / "accepted.json").read_text(encoding="utf-8"))
    assert registry[0]["id"] == "candidate-promote"
    assert registry[0]["issue"] == "https://example/issue/1"


def test_promote_test_moves_file(tmp_path: Path) -> None:
    (tmp_path / "backend" / "tests" / "agent").mkdir(parents=True)
    (tmp_path / "backend" / "tests" / "agent_accepted").mkdir(parents=True)
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "accepted.json").write_text("[]\n", encoding="utf-8")
    source = tmp_path / "backend" / "tests" / "agent" / "test_probe.py"
    source.write_text("def test_probe():\n    assert True\n", encoding="utf-8")
    meta = {
        "id": "candidate-test",
        "gap_type": "business_invariant",
        "artifact": "e2e_test",
        "summary": "probe",
        "test_file": "backend/tests/agent/test_probe.py",
        "invariant": "probe",
        "pre_fix_commit": "HEAD~1",
        "post_fix_commit": "HEAD",
        "incident_ref": "docs/incidents.md#probe",
    }
    candidate = _candidate(tmp_path, meta)
    entry = promote(candidate, _report(tmp_path, "business_invariant", "e2e_test"), tmp_path, "", POLICY)
    target = tmp_path / "backend" / "tests" / "agent_accepted" / "test_candidate_test.py"
    assert target.is_file()
    assert not source.exists()
    assert entry["target"] == "backend/tests/agent_accepted/test_candidate_test.py"


def test_non_promotable_artifact_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "docs" / "proposals").mkdir(parents=True)
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "accepted.json").write_text("[]\n", encoding="utf-8")
    proposal = tmp_path / "docs" / "proposals" / "design.md"
    proposal.write_text("# design\n", encoding="utf-8")
    meta = {
        "id": "candidate-adr",
        "gap_type": "internal_design",
        "artifact": "adr_proposal",
        "summary": "design",
        "artifact_file": "docs/proposals/design.md",
        "decision": "keep",
        "options": ["split", "keep"],
        "evidence": "none",
    }
    candidate = _candidate(tmp_path, meta)
    with pytest.raises(PromoteError, match="not auto-promotable"):
        promote(candidate, _report(tmp_path, "internal_design", "adr_proposal"), tmp_path, "", POLICY)


def test_failed_report_is_rejected(tmp_path: Path) -> None:
    candidate, _rule, report = _rule_repo(tmp_path)
    report.write_text(
        json.dumps({"verdict": "fail", "gap_type": "static_pattern", "artifact": "semgrep_rule"})
    )
    with pytest.raises(PromoteError, match="not pass"):
        promote(candidate, report, tmp_path, "", POLICY)


def test_duplicate_rule_is_rejected(tmp_path: Path) -> None:
    candidate, _rule, report = _rule_repo(tmp_path)
    (tmp_path / "rules" / "promoted.yml").write_text(
        "rules:\n  - id: promoted-probe\n    languages: [python]\n    severity: ERROR\n"
        "    message: existing\n    pattern: print(...)\n",
        encoding="utf-8",
    )
    with pytest.raises(PromoteError, match="already promoted"):
        promote(candidate, report, tmp_path, "", POLICY)


def test_existing_test_target_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "backend" / "tests" / "agent").mkdir(parents=True)
    (tmp_path / "backend" / "tests" / "agent_accepted").mkdir(parents=True)
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "accepted.json").write_text("[]\n", encoding="utf-8")
    source = tmp_path / "backend" / "tests" / "agent" / "test_probe.py"
    source.write_text("def test_probe():\n    assert True\n", encoding="utf-8")
    target = tmp_path / "backend" / "tests" / "agent_accepted" / "test_candidate_test.py"
    target.write_text("x = 1\n", encoding="utf-8")
    meta = {
        "id": "candidate-test",
        "gap_type": "business_invariant",
        "artifact": "e2e_test",
        "summary": "probe",
        "test_file": "backend/tests/agent/test_probe.py",
        "invariant": "probe",
        "pre_fix_commit": "HEAD~1",
        "post_fix_commit": "HEAD",
        "incident_ref": "docs/incidents.md#probe",
    }
    with pytest.raises(PromoteError, match="already exists"):
        promote(
            _candidate(tmp_path, meta),
            _report(tmp_path, "business_invariant", "e2e_test"),
            tmp_path,
            "",
            POLICY,
        )
