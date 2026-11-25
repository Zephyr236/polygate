"""Pure acceptance-contract policy used by Gherkin scenarios and CI."""

from __future__ import annotations

import argparse
import sys
from typing import Any

BLOCK = "block"
FOLLOW_UP = "follow-up"
ADVISORY = "advisory"
SEVERITY_ORDER = {"P2": 0, "P1": 1, "P0": 2}


def resolve_review_target(tested_head: str, current_head: str) -> str | None:
    """Return the head a review may use, or None for a stale completion."""
    return tested_head if tested_head == current_head else None


def is_superseded(started_at: str, statuses: list[dict[str, Any]]) -> bool:
    """Return True when a newer final design-review status already exists."""
    if not started_at:
        return False
    for status in statuses:
        if (
            status.get("context") == "design-review"
            and status.get("state") in {"success", "failure"}
            and str(status.get("created_at", "")) > started_at
        ):
            return True
    return False


def effective_severity(finding: dict[str, Any], requirements: dict[str, dict[str, Any]]) -> str:
    """Use the finding severity; fall back to the requirement or P2."""
    requirement = requirements.get(str(finding.get("requirement_id", "")))
    claimed = finding.get("severity")
    if claimed in SEVERITY_ORDER:
        return str(claimed)
    if requirement and requirement.get("severity") in SEVERITY_ORDER:
        return str(requirement["severity"])
    return "P2"


def decision_for_report(
    report: dict[str, Any],
    requirements: dict[str, dict[str, Any]],
    gate_result: str = "success",
) -> dict[str, Any]:
    """Apply the P0-only blocking policy to one review report."""
    if gate_result != "success":
        return {"status": BLOCK, "reason": "gate job did not succeed", "decisions": []}
    findings = report.get("findings")
    if not isinstance(findings, list):
        return {"status": BLOCK, "reason": "report has no findings list", "decisions": []}
    if report.get("verdict") != "pass" and not findings:
        return {"status": BLOCK, "reason": "needs-changes without a finding", "decisions": []}
    decisions = []
    for finding in findings:
        rid = finding.get("requirement_id")
        requirement = requirements.get(str(rid)) if rid else None
        severity = effective_severity(finding, requirements)
        if requirement is None and severity != "P0":
            decision = ADVISORY
        elif severity == "P0":
            decision = BLOCK
        elif severity == "P1":
            decision = FOLLOW_UP
        else:
            decision = ADVISORY
        decisions.append(
            {
                "title": str(finding.get("title", "")),
                "requirement_id": rid,
                "severity": severity,
                "decision": decision,
                "contract_gap": requirement is None,
            }
        )
    statuses = {item["decision"] for item in decisions}
    status = BLOCK if BLOCK in statuses else FOLLOW_UP if FOLLOW_UP in statuses else ADVISORY
    return {"status": status, "decisions": decisions}


def main() -> int:
    """CLI used by the workflow to verify the tested head."""
    parser = argparse.ArgumentParser(description="Gate head policy")
    parser.add_argument("--tested", required=True)
    parser.add_argument("--current", required=True)
    options = parser.parse_args()
    target = resolve_review_target(options.tested, options.current)
    if target is None:
        print(f"stale head: tested={options.tested} current={options.current}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
