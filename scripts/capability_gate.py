"""Check workflow capability splits against the contract."""

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


def _check_workflow(workflow: dict[str, Any], spec: dict[str, Any], name: str) -> list[str]:
    violations: list[str] = []
    top = workflow.get("permissions") or {}
    jobs = workflow.get("jobs") or {}
    agent_job = str(spec.get("agent_job", ""))
    publish_job = str(spec.get("publish_job", ""))
    agent = jobs.get(agent_job) or {}
    publish = jobs.get(publish_job) or {}
    agent_permissions = _permissions(agent, top)
    publish_permissions = _permissions(publish, top)
    for permission in spec.get("top_level_forbidden", []):
        scope, _, value = str(permission).partition(": ")
        if str(top.get(scope, "")) == value:
            violations.append(f"{name}: top-level permission {scope}: {value} is forbidden")
    for scope, value in agent_permissions.items():
        if value == "write":
            violations.append(f"{name}: agent job has forbidden write permission {scope}")
    for permission in spec.get("agent_forbidden", []):
        scope, _, value = str(permission).partition(": ")
        if agent_permissions.get(scope) == value:
            violations.append(f"{name}: agent job has forbidden permission {scope}: {value}")
    for permission in spec.get("publish_required", []):
        scope, _, value = str(permission).partition(": ")
        if publish_permissions.get(scope) != value:
            violations.append(f"{name}: publish job is missing {scope}: {value}")
    agent_text = json.dumps(agent)
    publish_text = json.dumps(publish)
    if str(spec.get("agent_command")) not in agent_text:
        violations.append(f"{name}: agent job does not run the trusted command")
    if spec.get("agent_no_publish") and "--no-publish" not in agent_text:
        violations.append(f"{name}: agent job does not pass --no-publish")
    if spec.get("publish_command") and str(spec["publish_command"]) not in publish_text:
        violations.append(f"{name}: publish job does not run the trusted publisher")
    return violations


def check(workflow_dir: Path, spec_path: Path) -> list[str]:
    """Return capability violations across all declared workflows."""
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for name, workflow_spec in (spec.get("workflows") or {}).items():
        path = workflow_dir / name
        if not path.is_file():
            violations.append(f"{name}: workflow file is missing")
            continue
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        violations.extend(_check_workflow(workflow, workflow_spec, name))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check workflow capabilities")
    parser.add_argument("--workflow-dir", type=Path, default=Path(".github/workflows"))
    parser.add_argument("--contract", type=Path, default=Path("specs/capabilities.yaml"))
    options = parser.parse_args()
    violations = check(options.workflow_dir, options.contract)
    if violations:
        print("\n".join(violations))
        return 1
    print("capability contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
