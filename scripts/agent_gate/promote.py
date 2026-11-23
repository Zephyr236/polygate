"""Promote an accepted candidate into the active rule or test suite."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from agent_gate.policy import ArtifactSpec, PolicyError, ensure_inside, load_policy

REGISTRY = "agent/accepted.json"
ARTIFACT_FIELDS = ("rule_file", "test_file", "artifact_file")
TEST_ARTIFACTS = {"property_test", "stateful_test", "e2e_test", "architecture_test"}


class PromoteError(ValueError):
    """Raised when a candidate cannot be promoted."""


def _source(repo: Path, meta: dict[str, Any], spec: ArtifactSpec) -> Path:
    for field_name in ARTIFACT_FIELDS:
        if str(meta.get(field_name, "")).strip():
            return ensure_inside(repo, str(meta[field_name]), spec.paths)
    raise PromoteError(f"artifact {spec.kind!r} has no artifact file")


def _test_passes_on_main(repo: Path, meta: dict[str, Any], artifact: str, source: Path) -> None:
    if artifact not in TEST_ARTIFACTS or not (repo / ".git").exists():
        return
    reference = "origin/main"
    if (
        subprocess.run(
            ["git", "rev-parse", "--verify", reference], cwd=repo, capture_output=True, check=False
        ).returncode
        != 0
    ):
        reference = "HEAD"
    worktree = Path(tempfile.mkdtemp(prefix="promote-check-"))
    try:
        added = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), reference],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if added.returncode != 0:
            raise PromoteError(f"cannot check out {reference}: {added.stderr.strip()[:200]}")
        relative = Path(str(meta["test_file"])).relative_to("backend")
        destination = worktree / str(meta["test_file"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        env = {
            **os.environ,
            "PYTHONPATH": str(worktree / "backend" / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(relative), "-q", "-p", "no:cacheprovider"],
            cwd=worktree / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode != 0:
            raise PromoteError("test does not pass on origin/main; merge the fixing PR first")
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        shutil.rmtree(worktree, ignore_errors=True)


def _check_report(report: dict[str, Any], meta: dict[str, Any]) -> None:
    if report.get("verdict") != "pass":
        raise PromoteError(f"candidate report verdict is {report.get('verdict')!r}, not pass")
    if report.get("artifact") != meta.get("artifact") or report.get("gap_type") != meta.get("gap_type"):
        raise PromoteError("report does not match the candidate gap type and artifact")


def _append_rule(source: Path, target: Path) -> None:
    try:
        incoming = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise PromoteError(f"candidate rule is not valid YAML: {error}") from error
    rules = incoming.get("rules") if isinstance(incoming, dict) else None
    if not isinstance(rules, list) or not rules:
        raise PromoteError("candidate rule file must contain a non-empty rules list")
    existing = yaml.safe_load(target.read_text(encoding="utf-8")) if target.is_file() else {"rules": []}
    if not isinstance(existing, dict) or not isinstance(existing.get("rules"), list):
        raise PromoteError(f"{target} is not a rules file")
    known = {str(rule.get("id")) for rule in existing["rules"] if isinstance(rule, dict)}
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("id"):
            raise PromoteError("every promoted rule needs an id")
        if str(rule["id"]) in known:
            raise PromoteError(f"rule id already promoted: {rule['id']}")
        existing["rules"].append(rule)
        known.add(str(rule["id"]))
    target.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True), encoding="utf-8")
    source.unlink()


def _move(source: Path, target: Path) -> None:
    if target.exists():
        raise PromoteError(f"promotion target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def _relative(repo: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def _registry_entry(
    repo: Path, meta: dict[str, Any], spec: ArtifactSpec, source: Path, target: Path, issue: str
) -> dict[str, Any]:
    return {
        "id": meta["id"],
        "artifact": meta["artifact"],
        "gap_type": meta["gap_type"],
        "issue": issue,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "oracle": spec.oracle,
        "source": _relative(repo, source),
        "target": _relative(repo, target),
        "fixtures": [str(meta.get("positive_fixture", "")), str(meta.get("negative_fixture", ""))],
        "invariant": str(meta.get("invariant", "")),
    }


def _update_registry(repo: Path, entry: dict[str, Any]) -> None:
    path = repo / REGISTRY
    document = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    if not isinstance(document, list):
        raise PromoteError(f"{REGISTRY} must be a JSON list")
    if any(item.get("id") == entry["id"] for item in document if isinstance(item, dict)):
        raise PromoteError(f"candidate already promoted: {entry['id']}")
    document.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def promote(
    candidate: Path, report_path: Path, repo: Path, issue: str = "", policy_path: Path | None = None
) -> dict[str, Any]:
    """Move an accepted artifact into the active suite and record it."""
    policy = load_policy(policy_path or repo / "agent" / "policy.toml")
    try:
        meta = json.loads(candidate.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PromoteError(f"cannot read candidate or report: {error}") from error
    if not isinstance(meta, dict) or not isinstance(report, dict):
        raise PromoteError("candidate and report must be JSON objects")
    try:
        spec = policy.decide(str(meta.get("gap_type", "")), str(meta.get("artifact", "")))
    except PolicyError as error:
        raise PromoteError(str(error)) from error
    if not spec.promotion:
        raise PromoteError(f"artifact {spec.kind!r} is not auto-promotable")
    _check_report(report, meta)
    source = _source(repo, meta, spec)
    _test_passes_on_main(repo, meta, spec.kind, source)
    if not source.is_file():
        raise PromoteError(f"artifact file not found: {source}")
    identifier = str(meta["id"])
    if spec.promotion.endswith(".py"):
        identifier = identifier.replace("-", "_")
    target = repo / spec.promotion.replace("<id>", identifier)
    if spec.promotion == "rules/promoted.yml":
        _append_rule(source, target)
    else:
        _move(source, target)
    entry = _registry_entry(repo, meta, spec, source, target, issue)
    _update_registry(repo, entry)
    return entry
