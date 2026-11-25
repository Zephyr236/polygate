"""Validate the requirement -> Gherkin -> BDD -> finding acceptance chain."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_contract

TAG = re.compile(r"req:([A-Z]+-\d+)")
P0 = re.compile(r"p0\b")
SCENARIO = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+)$")


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _feature_scenarios(features: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    by_requirement: dict[str, list[dict[str, Any]]] = {}
    names: list[str] = []
    for path in sorted(features.rglob("*.feature")):
        current: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("@"):
                current = [tag[1:] for tag in stripped.split() if tag.startswith("@")]
                continue
            match = SCENARIO.match(line)
            if not match:
                continue
            name = match.group(1).strip()
            names.append(name)
            tags = current or []
            current = []
            for tag in tags:
                requirement = TAG.fullmatch(tag)
                if requirement:
                    by_requirement.setdefault(requirement.group(1), []).append(
                        {"name": name, "p0": any(P0.fullmatch(item) for item in tags), "file": str(path)}
                    )
    return by_requirement, names


def _junit_results(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()  # noqa: S314 - trusted CI test report
    results: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = str(case.get("name", ""))
        failed = any(child.tag in {"failure", "error"} for child in case)
        results[name.lower()] = "failed" if failed else "passed"
    return results


def _scenario_result(name: str, results: dict[str, str]) -> str | None:
    needle = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_")
    for test_name, state in results.items():
        if needle in test_name.lower():
            return state
    return None


def _validate_requirements(document: dict[str, Any], root: Path, scope: dict[str, Any]) -> list[str]:
    requirements = document.get("requirements")
    if not isinstance(requirements, dict):
        return ["requirements must be a mapping"]
    problems: list[str] = []
    for rid, item in requirements.items():
        if not isinstance(item, dict):
            problems.append(f"{rid}: requirement must be a mapping")
            continue
        for field in ("title", "statement", "severity", "owner", "verify"):
            if not item.get(field):
                problems.append(f"{rid}: missing {field}")
        if item.get("severity") not in {"P0", "P1", "P2"}:
            problems.append(f"{rid}: invalid severity")
        for target in item.get("verify") or []:
            if not (root / str(target)).exists():
                problems.append(f"{rid}: verify target does not exist: {target}")
    for rid in scope.get("requirements") or []:
        if rid not in requirements:
            problems.append(f"scope references unknown requirement {rid}")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate the acceptance contract")
    parser.add_argument("--requirements", type=Path, default=Path("specs/requirements.yaml"))
    parser.add_argument("--scope", type=Path, default=Path("specs/scope.yaml"))
    parser.add_argument("--features", type=Path, default=Path("specs/features"))
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--allow-missing-results", action="store_true")
    parser.add_argument("--design-report", type=Path)
    parser.add_argument("--out", type=Path)
    options = parser.parse_args(argv[1:])
    root = Path.cwd()
    document = _load(options.requirements)
    scope = _load(options.scope)
    problems = _validate_requirements(document, root, scope)
    requirements = document.get("requirements") or {}
    by_requirement, scenario_names = _feature_scenarios(options.features)
    for rid in scope.get("requirements") or []:
        item = requirements.get(rid) or {}
        if item.get("severity") == "P0" and not by_requirement.get(rid):
            problems.append(f"{rid}: P0 requirement has no @req scenario")
    results = _junit_results(options.junit) if options.junit and options.junit.exists() else {}
    scope_p0 = [
        rid
        for rid in scope.get("requirements") or []
        if (requirements.get(rid) or {}).get("severity") == "P0"
    ]
    if scope_p0 and not results and not options.allow_missing_results:
        problems.append("JUnit results are required for a P0 scope")
    for rid, scenarios in by_requirement.items():
        for scenario in scenarios:
            if not scenario["p0"]:
                continue
            state = _scenario_result(scenario["name"], results) if results else None
            if state != "passed" and (results or not options.allow_missing_results):
                problems.append(f"{rid}: P0 scenario did not pass: {scenario['name']}")
    decision = {"status": "pass", "decisions": []}
    if options.design_report and options.design_report.exists():
        report = json.loads(options.design_report.read_text(encoding="utf-8"))
        decision = gate_contract.decision_for_report(report, requirements)
        if decision["status"] == gate_contract.BLOCK:
            problems.append("design report contains a blocking P0 finding")
    output = {
        "passed": not problems,
        "problems": problems,
        "scenarios": scenario_names,
        "requirements": len(requirements),
        "scope": scope.get("requirements") or [],
        "design_decision": decision["status"],
    }
    if options.out:
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
