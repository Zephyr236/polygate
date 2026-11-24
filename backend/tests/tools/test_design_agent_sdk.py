"""Tests for the single-agent Claude Agent SDK design reviewer."""

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
SCRIPT = REPO / "scripts" / "design_agent_sdk.py"
SPEC = importlib.util.spec_from_file_location("design_agent_sdk", SCRIPT)
assert SPEC and SPEC.loader
agent: types.ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


def _report() -> dict[str, Any]:
    return {
        "summary": "summary",
        "intent": "intent",
        "assumptions": ["a"],
        "invariants": ["i"],
        "alternatives": [{"option": "smaller", "tradeoffs": "less risk"}],
        "risks": ["r"],
        "missing_evidence": ["e"],
        "questions": ["q"],
        "verdict": "needs-discussion",
    }


def _install_fake_sdk(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: str | None = None,
    error: bool = False,
    structured: dict[str, Any] | None = None,
) -> None:
    class ResultMessage:
        def __init__(self) -> None:
            self.is_error = error
            self.subtype = "success"
            self.terminal_reason = "completed"
            self.result = result or json.dumps(_report())
            self.structured_output = structured

    async def query(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        yield ResultMessage()

    class Options:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    module = types.SimpleNamespace(ResultMessage=ResultMessage, query=query, ClaudeAgentOptions=Options)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)


def test_build_prompt_includes_the_brief() -> None:
    prompt = agent.build_prompt("brief text", "docs", "diff")
    assert "brief text" in prompt
    assert "Return only the JSON\nreport" in prompt


def test_dry_run_does_not_need_the_sdk(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert agent.main(["design_agent_sdk.py", "--diff-file", str(diff), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "senior design reviewer" in out
    assert "Return ONLY a JSON object" in out


def test_main_writes_one_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    brief = tmp_path / "brief.md"
    brief.write_text("brief", encoding="utf-8")
    out = tmp_path / "report.md"
    _install_fake_sdk(monkeypatch)
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    assert (
        agent.main(
            [
                "design_agent_sdk.py",
                "--diff-file",
                str(diff),
                "--brief",
                str(brief),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert "Design review" in out.read_text(encoding="utf-8")


def test_agent_error_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    _install_fake_sdk(monkeypatch, error=True)
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    assert agent.main(["design_agent_sdk.py", "--diff-file", str(diff)]) == 2


def test_run_query_returns_the_final_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sdk(monkeypatch)
    assert asyncio.run(agent.run_query("prompt", object()))["summary"] == "summary"


def test_run_query_prefers_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sdk(monkeypatch, structured=_report())
    report = asyncio.run(agent.run_query("prompt", object()))
    assert report["alternatives"][0]["option"] == "smaller"
