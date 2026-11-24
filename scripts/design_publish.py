"""Publish a design-gate report from a read-only agent job.

This runs in a separate job that never executes pull-request code. The agent job
only writes the report artifact; this job holds the write-scoped GitHub token.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_gate


def _failure_report(message: str) -> dict[str, Any]:
    return {
        "verdict": "needs-changes",
        "summary": message,
        "findings": [
            {
                "title": "Design gate could not complete",
                "path": "CI",
                "line": 1,
                "why": message,
                "evidence": "The gate failed before it could decide.",
                "fix": "Fix the gate failure and push again.",
            }
        ],
        "questions": [],
    }


def _load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return _failure_report(f"Design gate report is unavailable: {error}")
    if not isinstance(report, dict):
        return _failure_report("Design gate report is not an object")
    if report.get("verdict") not in {"pass", "needs-changes", "insufficient-context"}:
        return _failure_report("Design gate report has no valid verdict")
    findings = report.get("findings")
    if not isinstance(findings, list):
        return _failure_report("Design gate report has no findings list")
    return report


def main(argv: list[str]) -> int:
    """Publish status and blocking issues from a report artifact."""
    parser = argparse.ArgumentParser(description="Publish a design-gate report")
    parser.add_argument("--repo-slug", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--gate-result", default="success")
    parser.add_argument("--pending", action="store_true")
    options = parser.parse_args(argv[1:])
    try:
        if options.pending:
            design_gate.set_status(options.repo_slug, options.sha, "pending", "Design review running")
            return 0
        if options.gate_result != "success":
            report = _failure_report(f"Design gate job ended {options.gate_result}")
        else:
            report = _load_report(options.report) if options.report else _failure_report("No report path")
        findings = report.get("findings", [])
        design_gate.reconcile_issues(options.repo_slug, options.pr, options.sha, findings)
        passed = report.get("verdict") == "pass" and not findings
        design_gate.set_status(
            options.repo_slug,
            options.sha,
            "success" if passed else "failure",
            "Design gate passed" if passed else f"{len(findings)} blocking finding(s)",
        )
        return 0 if passed else 1
    except (design_gate.GateError, KeyError, TypeError) as error:
        print(f"design gate publication failed: {error}", file=sys.stderr)
        with contextlib.suppress(design_gate.GateError):
            design_gate.set_status(
                options.repo_slug, options.sha, "failure", "Design gate publication failed"
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
