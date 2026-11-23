"""Tests for the CodeQL severity gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "codeql_gate.py"
SPEC = importlib.util.spec_from_file_location("codeql_gate", SCRIPT)
assert SPEC and SPEC.loader
gate: ModuleType = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _sarif(*, severity: str | None = "9.1", level: str = "error", suppressed: bool = False) -> dict:
    rule = {"id": "py/test", "properties": {}}
    if severity is not None:
        rule["properties"]["security-severity"] = severity
    result = {
        "ruleId": "py/test",
        "ruleIndex": 0,
        "level": level,
        "message": {"text": "test finding"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "backend/src/x.py"},
                    "region": {"startLine": 4},
                }
            }
        ],
    }
    if suppressed:
        result["suppressions"] = [{"kind": "inSource"}]
    return {"runs": [{"tool": {"driver": {"rules": [rule]}}, "results": [result]}]}


def test_critical_blocks() -> None:
    assert gate.findings(_sarif(severity="9.1"))[0]["severity"] == 9.1


def test_high_blocks() -> None:
    assert gate.findings(_sarif(severity="7.0"))[0]["severity"] == 7.0


def test_medium_and_low_pass() -> None:
    assert gate.findings(_sarif(severity="6.9")) == []


def test_suppressed_passes() -> None:
    assert gate.findings(_sarif(suppressed=True)) == []


def test_error_without_severity_blocks() -> None:
    assert gate.findings(_sarif(severity=None, level="error"))[0]["severity"] == 7.0


def test_missing_directory_fails(tmp_path: Path) -> None:
    assert gate.main(["codeql_gate.py", str(tmp_path / "missing")]) == 2


def test_no_sarif_files_fails(tmp_path: Path) -> None:
    assert gate.main(["codeql_gate.py", str(tmp_path)]) == 2


def test_high_report_fails(tmp_path: Path) -> None:
    (tmp_path / "result.sarif").write_text(json.dumps(_sarif(severity="8.2")), encoding="utf-8")
    assert gate.main(["codeql_gate.py", str(tmp_path)]) == 1
