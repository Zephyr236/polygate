"""Tests for the advisory design review prototype."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "design_review.py"
SPEC = importlib.util.spec_from_file_location("design_review", SCRIPT)
assert SPEC and SPEC.loader
review: ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


def _report(**overrides: object) -> dict:
    report = {
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
    report.update(overrides)
    return report


def test_redact_hides_secret_values() -> None:
    assert "supersecret" not in review.redact("API_KEY=supersecret\n")


def test_extract_json_accepts_fenced_output() -> None:
    text = "```json\n" + json.dumps(_report()) + "\n```"
    assert review.extract_json(text)["verdict"] == "needs-discussion"


def test_extract_json_rejects_missing_keys() -> None:
    with pytest.raises(review.ReviewError, match="missing keys"):
        review.extract_json('{"summary": "x"}')


def test_build_prompt_requests_reasons_and_alternatives() -> None:
    prompt = review.build_prompt("diff", "docs")
    assert "Return ONLY a JSON object" in prompt
    assert "at least two alternatives" in prompt
    assert "Do not approve or reject" in prompt


def test_render_markdown_contains_sections() -> None:
    text = review.render_markdown(_report())
    assert "# Design review" in text
    assert "## Alternatives" in text
    assert "**smaller**" in text


def test_dry_run_prints_prompt_without_api_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert review.main(["design_review.py", "--diff-file", str(diff), "--dry-run"]) == 0
    assert "Return ONLY a JSON object" in capsys.readouterr().out
