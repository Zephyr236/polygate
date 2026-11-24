"""Tests for the required design gate."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "design_gate.py"
SPEC = importlib.util.spec_from_file_location("design_gate", SCRIPT)
assert SPEC and SPEC.loader
gate: types.ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _finding() -> dict[str, Any]:
    return {
        "title": "Problem",
        "path": "src/x.py",
        "line": 3,
        "why": "the why",
        "evidence": "evidence",
        "fix": "fix",
    }


def _pass() -> dict[str, Any]:
    return {"verdict": "pass", "summary": "ok", "findings": [], "questions": []}


def _install_fake_sdk(monkeypatch: pytest.MonkeyPatch, *, structured: dict[str, Any] | None = None) -> None:
    class ResultMessage:
        def __init__(self) -> None:
            self.is_error = False
            self.subtype = "success"
            self.terminal_reason = "completed"
            self.result = json.dumps(_pass())
            self.structured_output = structured

    async def query(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        yield ResultMessage()

    class Options:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(ResultMessage=ResultMessage, query=query, ClaudeAgentOptions=Options),
    )


def _run(tmp_path: Path, report: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> int:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    _install_fake_sdk(monkeypatch, structured=report)
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    return gate.main(
        [
            "design_gate.py",
            "--diff-file",
            str(diff),
            "--pr",
            "1",
            "--repo-slug",
            "",
            "--out",
            str(tmp_path / "report.json"),
        ]
    )


def test_fingerprint_is_stable_and_distinct() -> None:
    assert gate.fingerprint(_finding()) == gate.fingerprint(_finding())
    other = _finding()
    other["why"] = "different"
    assert gate.fingerprint(_finding()) != gate.fingerprint(other)


def test_issue_marker_round_trips() -> None:
    body = gate.issue_body(_finding(), 7, "abcdef123456")
    assert gate.parse_issue(body) == (7, gate.fingerprint(_finding()))


def test_pass_requires_no_findings() -> None:
    report = _pass()
    report["findings"] = [_finding()]
    assert gate._validate(report)["verdict"] == "needs-changes"


def test_needs_changes_without_findings_gets_a_blocking_finding() -> None:
    report = gate._validate(
        {"verdict": "needs-changes", "summary": "no finding", "findings": [], "questions": []}
    )
    assert report["findings"][0]["title"].startswith("Agent requested")


def test_insufficient_context_gets_a_blocking_finding() -> None:
    report = gate._validate(
        {"verdict": "insufficient-context", "summary": "no brief", "findings": [], "questions": []}
    )
    assert report["findings"][0]["title"].startswith("Design brief")


def test_main_passes_with_empty_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(tmp_path, _pass(), monkeypatch) == 0
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["verdict"] == "pass"


def test_main_fails_with_a_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = {"verdict": "needs-changes", "summary": "bad", "findings": [_finding()], "questions": []}
    assert _run(tmp_path, report, monkeypatch) == 1


def test_dry_run_prints_the_gate_prompt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert gate.main(["design_gate.py", "--diff-file", str(diff), "--pr", "1", "--dry-run"]) == 0
    assert "merge-gate design reviewer" in capsys.readouterr().out


def test_run_query_prefers_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sdk(monkeypatch, structured=_pass())
    assert asyncio.run(gate.run_query("prompt", object()))["verdict"] == "pass"
