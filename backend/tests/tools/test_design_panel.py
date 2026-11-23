"""Tests for the multi-role design review panel."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "design_panel.py"
SPEC = importlib.util.spec_from_file_location("design_panel", SCRIPT)
assert SPEC and SPEC.loader
panel: ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)


def _role_report(role: str) -> dict:
    return {
        "role": role,
        "verdict": "needs-decision",
        "findings": [f"{role} finding"],
        "questions": [f"{role} question"],
        "evidence": [f"{role} evidence"],
        "confidence": "medium",
    }


def _fake_complete(prompt: str, **kwargs: object) -> str:
    del kwargs
    for role in panel.ROLES:
        if f"You are the {role} reviewer" in prompt:
            return json.dumps(_role_report(role))
    raise panel.design_review.ReviewError("unknown role in prompt")


def test_roles_are_distinct() -> None:
    assert len(panel.ROLES) == len(set(panel.ROLES))
    assert "problem" in panel.ROLES


def test_parse_role_report_rejects_wrong_role() -> None:
    with pytest.raises(panel.PanelError, match="expected role"):
        panel.parse_role_report(json.dumps(_role_report("architecture")), "problem")


def test_parse_role_report_rejects_bad_verdict() -> None:
    report = _role_report("problem")
    report["verdict"] = "approve"
    with pytest.raises(panel.PanelError, match="invalid verdict"):
        panel.parse_role_report(json.dumps(report), "problem")


def test_panel_writes_one_report_per_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    brief = tmp_path / "brief.md"
    brief.write_text("problem: test\n", encoding="utf-8")
    out = tmp_path / "reports"
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    monkeypatch.setattr(panel.design_review, "complete", _fake_complete)
    assert (
        panel.main(
            [
                "design_panel.py",
                "--diff-file",
                str(diff),
                "--brief",
                str(brief),
                "--out-dir",
                str(out),
                "--roles",
                "problem,architecture",
            ]
        )
        == 0
    )
    assert (out / "problem.md").is_file()
    assert (out / "architecture.json").is_file()
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "problem" in index and "architecture" in index
    assert "needs-decision" in index


def test_panel_dry_run_prints_each_role(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert (
        panel.main(
            [
                "design_panel.py",
                "--diff-file",
                str(diff),
                "--dry-run",
                "--roles",
                "problem,evidence",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "===== problem =====" in out
    assert "===== evidence =====" in out
    assert "(no design brief supplied)" in out


def test_panel_unknown_role_fails(tmp_path: Path) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert panel.main(["design_panel.py", "--diff-file", str(diff), "--roles", "problem,unknown"]) == 2


def test_panel_partial_failure_writes_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    out = tmp_path / "reports"
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")

    def flaky(prompt: str, **kwargs: object) -> str:
        if "You are the security reviewer" in prompt:
            raise panel.design_review.ReviewError("security unavailable")
        return _fake_complete(prompt, **kwargs)

    monkeypatch.setattr(panel.design_review, "complete", flaky)
    assert (
        panel.main(
            [
                "design_panel.py",
                "--diff-file",
                str(diff),
                "--out-dir",
                str(out),
                "--roles",
                "problem,security",
            ]
        )
        == 2
    )
    assert (out / "problem.md").is_file()
    assert "security" in (out / "index.md").read_text(encoding="utf-8")
    assert "security unavailable" in (out / "index.md").read_text(encoding="utf-8")
