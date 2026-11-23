"""Tests for the advisory design review prototype."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "design_review.py"
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


def test_redact_hides_prefixed_and_quoted_secret_values() -> None:
    for text in (
        "API_KEY=supersecret\n",
        "ZEN_API_KEY=supersecret\n",
        "AMR_API_KEY=supersecret\n",
        "ADMIN_TOKEN=supersecret\n",
        'password = "hunter 2"\n',
    ):
        assert "supersecret" not in review.redact(text)
        assert "hunter 2" not in review.redact(text)


def test_extract_json_accepts_fenced_output() -> None:
    text = "```json\n" + json.dumps(_report()) + "\n```"
    assert review.extract_json(text)["verdict"] == "needs-discussion"


def test_extract_json_rejects_missing_keys() -> None:
    with pytest.raises(review.ReviewError, match="complete JSON report"):
        review.extract_json('{"summary": "x"}')


def test_extract_json_rejects_approval_verdict() -> None:
    with pytest.raises(review.ReviewError, match="verdict"):
        review.extract_json(json.dumps(_report(verdict="approve")))


def test_extract_json_rejects_wrong_field_type() -> None:
    with pytest.raises(review.ReviewError, match="risks"):
        review.extract_json(json.dumps(_report(risks="none")))


def test_extract_json_skips_prose_with_braces() -> None:
    text = "Schema fields {summary, intent}. Report:\n" + json.dumps(_report())
    assert review.extract_json(text)["summary"] == "summary"


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


def test_diff_file_is_capped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("A" * 1000 + "UNIQUE_TAIL", encoding="utf-8")
    assert (
        review.main(
            ["design_review.py", "--diff-file", str(diff), "--max-diff-chars", "100", "--dry-run"]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "[truncated]" in out
    assert "UNIQUE_TAIL" not in out


def test_empty_diff_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff = tmp_path / "empty.diff"
    diff.write_text("", encoding="utf-8")
    assert review.main(["design_review.py", "--diff-file", str(diff), "--dry-run"]) == 2
    assert "no changes" in capsys.readouterr().err


def test_main_writes_report_with_stubbed_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    out = tmp_path / "report.md"
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    monkeypatch.setattr(review, "complete", lambda *args, **kwargs: json.dumps(_report()))
    assert review.main(["design_review.py", "--diff-file", str(diff), "--out", str(out)]) == 0
    assert "Design review" in out.read_text(encoding="utf-8")


def _boom(*args: object, **kwargs: object) -> str:
    raise review.ReviewError("boom")


def test_main_returns_two_on_model_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    monkeypatch.setattr(review, "complete", _boom)
    assert review.main(["design_review.py", "--diff-file", str(diff)]) == 2
    assert "boom" in capsys.readouterr().err


def test_main_reports_output_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("diff --git a/x b/x\n", encoding="utf-8")
    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    monkeypatch.setattr(review, "complete", lambda *args, **kwargs: json.dumps(_report()))
    assert review.main(["design_review.py", "--diff-file", str(diff), "--out", str(tmp_path)]) == 2
    assert "design review failed" in capsys.readouterr().err


def test_collect_docs_reports_missing_documents(tmp_path: Path) -> None:
    assert review.collect_docs(tmp_path, None, 100) == "(no design documents found)"


def test_collect_docs_reads_the_reviewed_commit() -> None:
    assert "### AGENTS.md" in review.collect_docs(REPO, "HEAD", 20_000)


def test_main_redacts_before_the_model_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff = tmp_path / "x.diff"
    diff.write_text("ZEN_API_KEY=supersecret\n", encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_complete(prompt: str, **kwargs: object) -> str:
        del kwargs
        captured["prompt"] = prompt
        return json.dumps(_report())

    monkeypatch.setenv("DESIGN_REVIEW_API_KEY", "test")
    monkeypatch.setattr(review, "complete", fake_complete)
    assert review.main(["design_review.py", "--diff-file", str(diff)]) == 0
    assert "supersecret" not in captured["prompt"]
    assert "ZEN_API_KEY=<redacted>" in captured["prompt"]
