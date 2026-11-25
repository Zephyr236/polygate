"""Check the design-gate workflow's capability split against the contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _permissions(job: dict[str, Any], top: dict[str, Any]) -> dict[str, str]:
    merged = {str(k): str(v) for k, v in (top or {}).items()}
    merged.update({str(k): str(v) for k, v in (job.get("permissions") or {}).items()})
    return merged


def check(workflow_path: Path, spec_path: Path) -> list[str]:
    """Return capability violations in the workflow."""
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    top = workflow.get("permissions") or {}
    jobs = workflow.get("jobs") or {}
    for workflow_spec in (spec.get("workflows") or {}).values():
        agent_job = str(workflow_spec.get("agent_job", ""))
        publish_job = str(workflow_spec.get("publish_job", ""))
        agent = jobs.get(agent_job) or {}
        publish = jobs.get(publish_job) or {}
        agent_permissions = _permissions(agent, top)
        publish_permissions = _permissions(publish, top)
        for permission in workflow_spec.get("top_level_forbidden", []):
            scope, _, value = str(permission).partition(": ")
            if str(top.get(scope, "")) == value:
                violations.append(f"top-level permission {scope}: {value} is forbidden")
        for permission in workflow_spec.get("agent_forbidden", []):
            scope, _, value = str(permission).partition(": ")
            if agent_permissions.get(scope) == value:
                violations.append(f"agent job has forbidden permission {scope}: {value}")
        for permission in workflow_spec.get("publish_required", []):
            scope, _, value = str(permission).partition(": ")
            if publish_permissions.get(scope) != value:
                violations.append(f"publish job is missing {scope}: {value}")
        agent_text = json.dumps(agent)
        publish_text = json.dumps(publish)
        if str(workflow_spec.get("agent_command")) not in agent_text:
            violations.append("agent job does not run the trusted gate command")
        if "--no-publish" not in agent_text:
            violations.append("agent job does not pass --no-publish")
        if str(workflow_spec.get("publish_command")) not in publish_text:
            violations.append("publish job does not run the trusted publisher")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check workflow capabilities")
    parser.add_argument("--workflow", type=Path, default=Path(".github/workflows/design-gate.yml"))
    parser.add_argument("--contract", type=Path, default=Path("specs/capabilities.yaml"))
    options = parser.parse_args()
    violations = check(options.workflow, options.contract)
    if violations:
        print("\n".join(violations))
        return 1
    print("capability contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
