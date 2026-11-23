"""Tests for the agent-gate acceptance checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent_gate.accept import Report, _check_test_static, accept

REPO = Path(__file__).resolve().parents[3]
POLICY = REPO / "agent" / "policy.toml"


def _write_candidate(repo: Path, meta: dict[str, Any]) -> Path:
    path = repo / "agent" / "candidates" / str(meta["id"]) / "candidate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


def _fake_rule_run(cmd: list[str], cwd: Path, env: dict[str, str] | None, timeout: float) -> Any:
    del cwd, env, timeout
    target = str(cmd[-1])
    return SimpleNamespace(returncode=1 if "bad" in target else 0, stdout="", stderr="")


def _rule_meta(repo: Path, **overrides: Any) -> dict[str, Any]:
    (repo / "rules" / "candidates").mkdir(parents=True, exist_ok=True)
    (repo / "backend" / "src").mkdir(parents=True, exist_ok=True)
    for name in ("bad", "good"):
        (repo / "agent" / "fixtures" / name).mkdir(parents=True, exist_ok=True)
    (repo / "agent" / "fixtures" / "bad" / "bad.py").write_text("print('x')\n", encoding="utf-8")
    (repo / "agent" / "fixtures" / "good" / "good.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "rules" / "candidates" / "rule.yml").write_text(
        "rules:\n  - id: probe\n    languages: [python]\n    severity: ERROR\n"
        "    message: probe\n    pattern: print(...)\n",
        encoding="utf-8",
    )
    meta: dict[str, Any] = {
        "id": "candidate-001",
        "gap_type": "static_pattern",
        "artifact": "semgrep_rule",
        "summary": "probe rule",
        "rule_file": "rules/candidates/rule.yml",
        "positive_fixture": "agent/fixtures/bad",
        "negative_fixture": "agent/fixtures/good",
        "incident_ref": "docs/incidents.md#probe",
    }
    meta.update(overrides)
    return meta


def test_rule_candidate_passes_with_injected_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: "/usr/bin/semgrep")
    meta = _rule_meta(tmp_path)
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "pass", [check.__dict__ for check in report.checks]


def test_rule_that_never_fires_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: "/usr/bin/semgrep")
    meta = _rule_meta(tmp_path)
    silent = lambda *_: SimpleNamespace(returncode=0, stdout="", stderr="")  # noqa: E731
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=silent)
    assert report.verdict == "fail"
    assert any(check.name == "rule_positive" and check.status == "fail" for check in report.checks)


def test_overfit_rule_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: "/usr/bin/semgrep")
    meta = _rule_meta(tmp_path)
    (tmp_path / "rules" / "candidates" / "rule.yml").write_text(
        "rules:\n  - id: probe\n    paths:\n      include:\n        - /root/secret.py\n"
        "    pattern: print(...)\n",
        encoding="utf-8",
    )
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "fail"
    assert any(check.name == "anti_overfit" and check.status == "fail" for check in report.checks)


def test_duplicate_rule_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: "/usr/bin/semgrep")
    meta = _rule_meta(tmp_path)
    body = (tmp_path / "rules" / "candidates" / "rule.yml").read_text(encoding="utf-8")
    (tmp_path / "rules" / "existing.yml").write_text(body, encoding="utf-8")
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "fail"
    assert any(check.name == "duplicates" and check.status == "fail" for check in report.checks)


def test_missing_tool_needs_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: None)
    meta = _rule_meta(tmp_path)
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "needs_human"


def test_schema_and_policy_mismatch_fail(tmp_path: Path) -> None:
    meta = _rule_meta(tmp_path)
    del meta["incident_ref"]
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "fail"
    mismatch = _rule_meta(tmp_path, gap_type="internal_design", artifact="e2e_test")
    report = accept(_write_candidate(tmp_path, mismatch), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "fail"


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    meta = _rule_meta(tmp_path, rule_file="../outside.yml")
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, run=_fake_rule_run)
    assert report.verdict == "fail"
    assert any(check.name == "paths" and check.status == "fail" for check in report.checks)


def test_human_artifact_needs_human(tmp_path: Path) -> None:
    (tmp_path / "docs" / "proposals").mkdir(parents=True)
    proposal = tmp_path / "docs" / "proposals" / "design.md"
    proposal.write_text("# decision\n", encoding="utf-8")
    meta = {
        "id": "candidate-adr",
        "gap_type": "internal_design",
        "artifact": "adr_proposal",
        "summary": "split the scheduler module",
        "artifact_file": "docs/proposals/design.md",
        "decision": "keep one module",
        "options": ["split", "keep"],
        "evidence": "proposal",
    }
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY)
    assert report.verdict == "needs_human"


def test_test_static_rejects_network_imports(tmp_path: Path) -> None:
    test_file = tmp_path / "test_network.py"
    test_file.write_text("import socket\n\ndef test_x():\n    assert socket\n", encoding="utf-8")
    report = Report("x", "business_invariant", "e2e_test", "auto")
    _check_test_static(report, test_file)
    assert report.checks[0].status == "fail"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_pre_post_oracle_passes_with_real_git(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "backend" / "tests" / "agent").mkdir(parents=True)
    (tmp_path / "backend" / "src").mkdir(parents=True)
    (tmp_path / "backend" / "tests" / "agent" / ".gitkeep").write_text("", encoding="utf-8")
    pre = _commit(tmp_path, "pre")
    (tmp_path / "feature.txt").write_text("feature\n", encoding="utf-8")
    _commit(tmp_path, "post")
    test_file = tmp_path / "backend" / "tests" / "agent" / "test_feature.py"
    test_file.write_text(
        "from pathlib import Path\n\n\ndef test_feature():\n"
        '    assert (Path(__file__).resolve().parents[3] / "feature.txt").exists()\n',
        encoding="utf-8",
    )
    meta = {
        "id": "candidate-test",
        "gap_type": "business_invariant",
        "artifact": "e2e_test",
        "summary": "feature must persist",
        "test_file": "backend/tests/agent/test_feature.py",
        "invariant": "feature.txt exists after the fix",
        "pre_fix_commit": pre,
        "post_fix_commit": "HEAD",
        "incident_ref": "docs/incidents.md#feature",
    }
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, soak=2)
    assert report.verdict == "pass", [check.__dict__ for check in report.checks]
    assert _git(tmp_path, "worktree", "list").count("\n") == 0


def test_fixture_command_oracle(tmp_path: Path) -> None:
    (tmp_path / "scripts" / "agent_checks").mkdir(parents=True)
    (tmp_path / "scripts" / "agent_checks" / "check.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "agent" / "fixtures" / "bad").mkdir(parents=True)
    (tmp_path / "agent" / "fixtures" / "good").mkdir(parents=True)
    (tmp_path / "agent" / "fixtures" / "bad" / "bad.txt").write_text("bad\n", encoding="utf-8")
    meta = {
        "id": "candidate-deploy",
        "gap_type": "deployment_policy",
        "artifact": "deploy_check",
        "summary": "detect an exposed port",
        "artifact_file": "scripts/agent_checks/check.py",
        "invariant": "no public bind",
        "command": [
            "python",
            "-c",
            "import pathlib,sys; sys.exit(1 if pathlib.Path('bad.txt').exists() else 0)",
        ],
        "positive_fixture": "agent/fixtures/bad",
        "negative_fixture": "agent/fixtures/good",
        "incident_ref": "docs/incidents.md#port",
    }
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY)
    assert report.verdict == "pass", [check.__dict__ for check in report.checks]


def test_static_only_skips_missing_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_gate.accept.shutil.which", lambda _: None)
    meta = _rule_meta(tmp_path)
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, static_only=True)
    assert report.verdict == "pass", [check.__dict__ for check in report.checks]
    assert any(check.name == "runtime_oracle" and check.status == "skip" for check in report.checks)


def test_static_only_test_checks_paths_and_imports(tmp_path: Path) -> None:
    (tmp_path / "backend" / "tests" / "agent").mkdir(parents=True)
    (tmp_path / "backend" / "tests" / "agent" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    meta = {
        "id": "candidate-static-test",
        "gap_type": "business_invariant",
        "artifact": "e2e_test",
        "summary": "static check only",
        "test_file": "backend/tests/agent/test_ok.py",
        "invariant": "nothing",
        "pre_fix_commit": "HEAD",
        "post_fix_commit": "HEAD",
        "incident_ref": "docs/incidents.md#static",
    }
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, static_only=True)
    assert report.verdict == "pass", [check.__dict__ for check in report.checks]

    (tmp_path / "backend" / "tests" / "agent" / "test_ok.py").write_text(
        "import socket\n\ndef test_ok():\n    assert socket\n", encoding="utf-8"
    )
    report = accept(_write_candidate(tmp_path, meta), tmp_path, POLICY, static_only=True)
    assert report.verdict == "fail"
