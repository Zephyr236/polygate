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
import gate_contract


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
                "requirement_id": "GATE-006",
                "severity": "P0",
                "doc_ref": "docs/acceptance-contract.md#finding-policy",
            }
        ],
        "questions": [],
    }


def _superseded(repo: str, sha: str, started_at: str) -> bool:
    """Skip a run when a newer final design-review status already exists."""
    if not started_at:
        return False
    statuses = design_gate._gh("GET", f"/repos/{repo}/commits/{sha}/statuses?per_page=100")
    return gate_contract.is_superseded(started_at, statuses if isinstance(statuses, list) else [])


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
    parser.add_argument("--started-at", default="")
    parser.add_argument("--requirements", type=Path, default=Path("specs/requirements.yaml"))
    parser.add_argument("--pending", action="store_true")
    options = parser.parse_args(argv[1:])
    try:
        if options.pending:
            design_gate.set_status(options.repo_slug, options.sha, "pending", "Design review running")
            return 0
        if _superseded(options.repo_slug, options.sha, options.started_at):
            print("a newer design-review status already exists; skipping", file=sys.stderr)
            return 0
        requirements = design_gate.load_requirements(options.requirements)
        if options.gate_result != "success":
            report = _failure_report(f"Design gate job ended {options.gate_result}")
        else:
            report = _load_report(options.report) if options.report else _failure_report("No report path")
        decision = gate_contract.decision_for_report(report, requirements, options.gate_result)
        findings = report.get("findings", [])
        decisions = decision.get("decisions", [])
        blocking = [
            finding
            for finding, item in zip(findings, decisions, strict=False)
            if item.get("decision") == gate_contract.BLOCK
        ]
        if decision["status"] == gate_contract.BLOCK and not blocking:
            report = _failure_report("Design gate could not produce an actionable decision")
            blocking = report["findings"]
        design_gate.reconcile_issues(options.repo_slug, options.pr, options.sha, blocking)
        passed = decision["status"] != gate_contract.BLOCK
        design_gate.set_status(
            options.repo_slug,
            options.sha,
            "success" if passed else "failure",
            "Design gate passed" if passed else f"{len(blocking)} blocking finding(s)",
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
