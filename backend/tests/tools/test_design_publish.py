"""Tests for publishing design-gate reports."""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "design_publish.py"
SPEC = importlib.util.spec_from_file_location("design_publish", SCRIPT)
assert SPEC and SPEC.loader
publish: types.ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


def _report(tmp_path: Path, report: dict[str, object]) -> Path:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _args(report: Path) -> list[str]:
    return [
        "design_publish.py",
        "--repo-slug",
        "o/r",
        "--pr",
        "1",
        "--sha",
        "abc",
        "--report",
        str(report),
    ]


def test_publish_pass_sets_success(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(publish.design_gate, "set_status", lambda *args: calls.append(args))
    monkeypatch.setattr(publish.design_gate, "reconcile_issues", lambda *args: None)
    report = _report(tmp_path, {"verdict": "pass", "summary": "ok", "findings": [], "questions": []})
    assert publish.main(_args(report)) == 0
    assert calls[-1][2] == "success"


def test_publish_missing_report_fails_closed(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(publish.design_gate, "set_status", lambda *args: calls.append(args))
    monkeypatch.setattr(publish.design_gate, "reconcile_issues", lambda *args: None)
    assert publish.main(_args(tmp_path / "missing.json")) == 1
    assert calls[-1][2] == "failure"


def test_pending_marks_the_review(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(publish.design_gate, "set_status", lambda *args: calls.append(args))
    args = [*_args(tmp_path / "missing.json"), "--pending"]
    assert publish.main(args) == 0
    assert calls[-1][2] == "pending"
