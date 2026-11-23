"""Fail when CodeQL reports high or critical severity findings."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

HIGH = 7.0


class GateError(RuntimeError):
    """Raised when SARIF cannot be evaluated."""


def _severity(
    result: dict[str, Any], rules: dict[int, dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> float | None:
    properties = result.get("properties", {})
    if isinstance(properties, dict) and properties.get("security-severity") is not None:
        try:
            return float(properties["security-severity"])
        except (TypeError, ValueError):
            return None
    index = result.get("ruleIndex")
    rule = rules.get(index) if isinstance(index, int) else None
    if rule is None:
        rule = by_id.get(str(result.get("ruleId", "")))
    if isinstance(rule, dict):
        rule_properties = rule.get("properties", {})
        if isinstance(rule_properties, dict) and rule_properties.get("security-severity") is not None:
            try:
                return float(rule_properties["security-severity"])
            except (TypeError, ValueError):
                return None
    return None


def findings(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Return unsuppressed high or critical findings from one SARIF document."""
    found: list[dict[str, Any]] = []
    for run in document.get("runs", []) or []:
        if not isinstance(run, dict):
            continue
        tool = run.get("tool", {}) or {}
        driver = tool.get("driver", {}) if isinstance(tool, dict) else {}
        rules: dict[int, dict[str, Any]] = {}
        by_id: dict[str, dict[str, Any]] = {}
        if isinstance(driver, dict):
            for index, rule in enumerate(driver.get("rules", []) or []):
                if isinstance(rule, dict):
                    rules[index] = rule
                    if rule.get("id") is not None:
                        by_id[str(rule["id"])] = rule
        for result in run.get("results", []) or []:
            if not isinstance(result, dict) or result.get("suppressions"):
                continue
            severity = _severity(result, rules, by_id)
            if severity is None and result.get("level") == "error":
                severity = HIGH
            if severity is None or severity < HIGH:
                continue
            location = ""
            locations = result.get("locations", []) or []
            if locations and isinstance(locations[0], dict):
                physical = locations[0].get("physicalLocation", {}) or {}
                artifact = physical.get("artifactLocation", {}) or {}
                region = physical.get("region", {}) or {}
                location = f"{artifact.get('uri', '?')}:{region.get('startLine', '?')}"
            found.append(
                {
                    "rule": result.get("ruleId", "?"),
                    "severity": severity,
                    "location": location,
                    "message": " ".join(str((result.get("message") or {}).get("text", "")).split())[:240],
                }
            )
    return found


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict):
        raise GateError(f"{path} is not a SARIF object")
    return document


def main(argv: list[str]) -> int:
    """Evaluate SARIF files and fail on high or critical findings."""
    if len(argv) != 2:
        print("usage: codeql_gate.py <sarif-directory>", file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"CodeQL gate: SARIF directory not found: {root}", file=sys.stderr)
        return 2
    paths = sorted(root.rglob("*.sarif")) + sorted(root.rglob("*.sarif.gz"))
    if not paths:
        print(f"CodeQL gate: no SARIF files under {root}", file=sys.stderr)
        return 2
    blocked: list[dict[str, Any]] = []
    try:
        for path in paths:
            blocked.extend(findings(_load(path)))
    except GateError as error:
        print(f"CodeQL gate: {error}", file=sys.stderr)
        return 2
    if not blocked:
        print(f"CodeQL gate: no high or critical findings in {len(paths)} SARIF file(s)")
        return 0
    print(f"CodeQL gate: {len(blocked)} high/critical finding(s)")
    for item in blocked:
        print(f"- [{item['severity']:.1f}] {item['rule']} {item['location']} {item['message']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
