"""Accept or reject an agent-proposed gate candidate against deterministic oracles."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_gate.policy import ArtifactSpec, Policy, PolicyError, ensure_inside, load_policy

Runner = Callable[[list[str], Path, dict[str, str] | None, float], subprocess.CompletedProcess[str]]

DENIED_TEST_IMPORTS = {"socket", "subprocess", "requests", "httpx", "urllib"}
ALLOWED_COMMAND_PREFIXES = {"python", "python3", "uv", "pytest", "lint-imports", "dependency-cruise"}
FIXTURE_PREFIXES = ("agent/",)
ARTIFACT_FIELDS = ("rule_file", "test_file", "artifact_file")


@dataclass
class Check:
    """One acceptance check result."""

    name: str
    status: str
    detail: str = ""


@dataclass
class Report:
    """The full acceptance report."""

    candidate: str
    gap_type: str
    artifact: str
    acceptance: str
    checks: list[Check] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """Return fail, needs_human or pass."""
        if any(check.status == "fail" for check in self.checks):
            return "fail"
        if self.acceptance == "human" or any(check.status == "needs_human" for check in self.checks):
            return "needs_human"
        return "pass"

    def as_dict(self) -> dict[str, Any]:
        """Serialize the report for CI output."""
        return {
            "candidate": self.candidate,
            "gap_type": self.gap_type,
            "artifact": self.artifact,
            "acceptance": self.acceptance,
            "verdict": self.verdict,
            "checks": [check.__dict__ for check in self.checks],
        }


def _run(
    cmd: list[str], cwd: Path, env: dict[str, str] | None, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run a command with captured output."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)


def _add(report: Report, name: str, ok: bool, detail: str = "") -> None:
    report.checks.append(Check(name, "pass" if ok else "fail", detail))


def _human(report: Report, name: str, detail: str) -> None:
    report.checks.append(Check(name, "needs_human", detail))


def _text(meta: dict[str, Any], field_name: str) -> str:
    return str(meta.get(field_name, "")).strip()


def _fixture_path(repo: Path, meta: dict[str, Any], field_name: str) -> Path:
    return ensure_inside(repo, _text(meta, field_name), FIXTURE_PREFIXES)


def _artifact_path(repo: Path, meta: dict[str, Any], spec: ArtifactSpec) -> Path:
    for field_name in ARTIFACT_FIELDS:
        if _text(meta, field_name):
            return ensure_inside(repo, _text(meta, field_name), spec.paths)
    raise PolicyError(f"artifact {spec.kind!r} needs one of {', '.join(ARTIFACT_FIELDS)}")


def _check_schema(report: Report, meta: dict[str, Any], policy: Policy) -> ArtifactSpec | None:
    for field_name in ("id", "gap_type", "artifact", "summary"):
        if not _text(meta, field_name):
            _add(report, "schema", False, f"missing field: {field_name}")
            return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", _text(meta, "id")):
        _add(report, "schema", False, "id must be lowercase letters, digits and dashes")
        return None
    try:
        spec = policy.decide(_text(meta, "gap_type"), _text(meta, "artifact"))
    except PolicyError as error:
        _add(report, "policy", False, str(error))
        return None
    missing = policy.missing_fields(_text(meta, "artifact"), meta)
    if missing:
        _add(report, "schema", False, f"missing required fields: {', '.join(missing)}")
        return None
    _add(report, "schema", True, f"{_text(meta, 'gap_type')} -> {_text(meta, 'artifact')}")
    return spec


def _check_paths(report: Report, repo: Path, meta: dict[str, Any], spec: ArtifactSpec) -> bool:
    try:
        artifact = _artifact_path(repo, meta, spec)
        if not artifact.is_file():
            raise PolicyError(f"artifact file not found: {artifact}")
        for field_name in ("positive_fixture", "negative_fixture"):
            if _text(meta, field_name):
                fixture = _fixture_path(repo, meta, field_name)
                if not fixture.exists():
                    raise PolicyError(f"fixture not found: {fixture}")
    except PolicyError as error:
        _add(report, "paths", False, str(error))
        return False
    _add(report, "paths", True, str(artifact.relative_to(repo)))
    return True


def _check_budget(report: Report, repo: Path, policy: Policy) -> None:
    root = repo / "agent" / "candidates"
    count = len(list(root.glob("*/candidate.json"))) if root.is_dir() else 0
    _add(report, "budget", count <= policy.max_candidates, f"{count}/{policy.max_candidates} candidates")


def _fingerprint(path: Path) -> str:
    body = re.sub(r"#.*", "", path.read_text(encoding="utf-8"))
    return hashlib.sha256(" ".join(body.split()).encode()).hexdigest()


def _check_duplicates(report: Report, repo: Path, artifact: Path) -> None:
    own = _fingerprint(artifact)
    directories = ("rules", "backend/tests", "frontend/tests")
    for directory in directories:
        root = repo / directory
        if not root.is_dir():
            continue
        for candidate in root.rglob("*"):
            if not candidate.is_file() or candidate.suffix not in {".yml", ".yaml", ".py"}:
                continue
            if candidate.resolve() == artifact.resolve():
                continue
            if _fingerprint(candidate) == own:
                _add(
                    report,
                    "duplicates",
                    False,
                    f"identical artifact already exists: {candidate.relative_to(repo)}",
                )
                return
    _add(report, "duplicates", True)


def _check_rule_text(report: Report, artifact: Path, meta: dict[str, Any]) -> None:
    text = artifact.read_text(encoding="utf-8")
    problems: list[str] = []
    if re.search(r"/root/|/home/|[A-Za-z]:\\\\", text):
        problems.append("absolute path in rule")
    if re.search(r"\b[0-9a-f]{40}\b", text):
        problems.append("commit hash in rule")
    for line in text.splitlines():
        if line.strip().startswith("pattern-regex:") and len(line) > 160:
            problems.append("pattern-regex is too literal (overfit)")
        if line.strip().startswith("- ") and line.rstrip().endswith(".py") and "*" not in line:
            problems.append("paths targets a single file (overfit)")
    excerpt = _text(meta, "incident_excerpt")
    if len(excerpt) >= 40 and excerpt in text:
        problems.append("rule embeds the incident text (overfit)")
    _add(report, "anti_overfit", not problems, "; ".join(problems))


def _check_test_static(report: Report, artifact: Path) -> None:
    try:
        tree = ast.parse(artifact.read_text(encoding="utf-8"))
    except SyntaxError as error:
        _add(report, "test_static", False, f"invalid Python: {error.msg}")
        return
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            problems.extend(
                f"imports {item.name}"
                for item in node.names
                if item.name.split(".")[0] in DENIED_TEST_IMPORTS
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in DENIED_TEST_IMPORTS:
                problems.append(f"imports {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "time"
                and node.func.attr == "sleep"
            ):
                problems.append("calls time.sleep")
    _add(report, "test_static", not problems, "; ".join(problems))


def _tool_base(kind: str, repo: Path) -> list[str] | None:
    if kind == "semgrep_rule":
        found = shutil.which("semgrep")
        if found:
            return [found]
        if (repo / "backend" / "pyproject.toml").is_file():
            return ["uv", "run", "--project", "backend", "semgrep"]
        return None
    found = shutil.which("ast-grep")
    return [found] if found else None


def _rule_command(base: list[str], rule: Path, target: Path) -> list[str]:
    if "semgrep" in base[-1]:
        return [
            *base,
            "scan",
            "--config",
            str(rule),
            "--error",
            "--quiet",
            "--no-git-ignore",
            "--exclude",
            ".venv",
            "--exclude",
            "node_modules",
            "--exclude",
            "frontend/dist",
            "--exclude",
            "mutants",
            "--exclude",
            "site",
            str(target),
        ]
    return [*base, "scan", "--rule", str(rule), str(target)]


def _check_rule(report: Report, repo: Path, meta: dict[str, Any], spec: ArtifactSpec, run: Runner) -> None:
    base = _tool_base(spec.kind, repo)
    if base is None:
        _human(report, "rule_oracle", f"{spec.kind} tool is not installed")
        return
    rule = _artifact_path(repo, meta, spec)
    positive = _fixture_path(repo, meta, "positive_fixture")
    negative = _fixture_path(repo, meta, "negative_fixture")
    try:
        positive_result = run(_rule_command(base, rule, positive), repo, None, 120)
        negative_result = run(_rule_command(base, rule, negative), repo, None, 120)
        current_result = run(_rule_command(base, rule, repo / "backend" / "src"), repo, None, 300)
    except (OSError, subprocess.TimeoutExpired) as error:
        _add(report, "rule_oracle", False, str(error))
        return
    _add(report, "rule_positive", positive_result.returncode != 0, "must fire on the violation fixture")
    _add(report, "rule_negative", negative_result.returncode == 0, "must stay silent on the clean fixture")
    _add(
        report, "rule_current", current_result.returncode == 0, "must stay silent on the current source tree"
    )


def _check_test_static_and_paths(report: Report, repo: Path, meta: dict[str, Any]) -> Path | None:
    try:
        test_file = ensure_inside(repo, _text(meta, "test_file"), ("backend/tests/agent/",))
    except PolicyError as error:
        _human(report, "test_path", str(error))
        return None
    _check_test_static(report, test_file)
    return test_file


def _worktree(repo: Path, commit: str, run: Runner) -> Path:
    target = Path(tempfile.mkdtemp(prefix="agent-gate-"))
    result = run(["git", "worktree", "add", "--detach", str(target), commit], repo, None, 120)
    if result.returncode != 0:
        raise PolicyError(f"cannot create worktree at {commit}: {result.stderr.strip()[:200]}")
    return target


def _remove_worktree(repo: Path, target: Path, run: Runner) -> None:
    run(["git", "worktree", "remove", "--force", str(target)], repo, None, 120)
    shutil.rmtree(target, ignore_errors=True)


def _run_in_worktree(test_file: str, worktree: Path, run: Runner) -> subprocess.CompletedProcess[str]:
    relative = Path(test_file).relative_to("backend")
    env = {
        **os.environ,
        "PYTHONPATH": str(worktree / "backend" / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    cmd = [sys.executable, "-m", "pytest", str(relative), "-q", "-p", "no:cacheprovider"]
    return run(cmd, worktree / "backend", env, 300)


def _check_pre_post(report: Report, repo: Path, meta: dict[str, Any], run: Runner, soak: int) -> None:
    test_file = _check_test_static_and_paths(report, repo, meta)
    if test_file is None:
        return
    commits = (_text(meta, "pre_fix_commit"), _text(meta, "post_fix_commit"))
    for commit in commits:
        if not re.fullmatch(r"[0-9a-zA-Z_./~^-]{4,64}", commit):
            _add(report, "commits", False, f"invalid commit reference: {commit}")
            return
        checked = run(["git", "rev-parse", "--verify", commit], repo, None, 30)
        if checked.returncode != 0:
            _add(report, "commits", False, f"unknown commit: {commit}")
            return
    pre = post = None
    try:
        pre = _worktree(repo, commits[0], run)
        post = _worktree(repo, commits[1], run)
        for worktree in (pre, post):
            destination = worktree / _text(meta, "test_file")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(test_file, destination)
        pre_result = _run_in_worktree(_text(meta, "test_file"), pre, run)
        post_results = [_run_in_worktree(_text(meta, "test_file"), post, run) for _ in range(soak)]
    except (PolicyError, OSError, subprocess.TimeoutExpired) as error:
        _add(report, "pre_post", False, str(error))
        return
    finally:
        if pre is not None:
            _remove_worktree(repo, pre, run)
        if post is not None:
            _remove_worktree(repo, post, run)
    _add(report, "pre_fix_fails", pre_result.returncode != 0, "test must fail before the fix")
    _add(
        report,
        "post_fix_passes",
        all(item.returncode == 0 for item in post_results),
        f"test must pass after the fix ({soak}x)",
    )


def _command_allowed(command: Any) -> bool:
    if not isinstance(command, list) or not command:
        return False
    head = Path(str(command[0])).name
    return head in ALLOWED_COMMAND_PREFIXES


def _check_fixture_command(report: Report, repo: Path, meta: dict[str, Any], run: Runner) -> None:
    command = meta.get("command")
    if not _command_allowed(command):
        _add(
            report,
            "fixture_command",
            False,
            f"command head must be one of {sorted(ALLOWED_COMMAND_PREFIXES)}",
        )
        return
    try:
        positive = _fixture_path(repo, meta, "positive_fixture")
        negative = _fixture_path(repo, meta, "negative_fixture")
    except PolicyError as error:
        _add(report, "fixture_command", False, str(error))
        return
    if not positive.is_dir() or not negative.is_dir():
        _add(report, "fixture_command", False, "fixtures must be directories for fixture_command")
        return
    try:
        bad = run([str(item) for item in command], positive, None, 120)
        good = run([str(item) for item in command], negative, None, 120)
    except (OSError, subprocess.TimeoutExpired) as error:
        _add(report, "fixture_command", False, str(error))
        return
    _add(report, "fixture_positive", bad.returncode != 0, "command must fail on the violation fixture")
    _add(report, "fixture_negative", good.returncode == 0, "command must pass on the clean fixture")


def _check_static_oracle(report: Report, repo: Path, meta: dict[str, Any], spec: ArtifactSpec) -> None:
    if spec.oracle == "rule":
        _check_rule_text(report, _artifact_path(repo, meta, spec), meta)
    elif spec.oracle == "pre_post":
        _check_test_static_and_paths(report, repo, meta)
    elif spec.oracle == "fixture_command":
        if not _command_allowed(meta.get("command")):
            _add(report, "fixture_command", False, "command head is not allowed")
        else:
            for field_name in ("positive_fixture", "negative_fixture"):
                try:
                    fixture = _fixture_path(repo, meta, field_name)
                except PolicyError as error:
                    _add(report, "fixtures", False, str(error))
                    return
                if not fixture.is_dir():
                    _add(report, "fixtures", False, f"{field_name} must be a directory")
                    return
            _add(report, "fixtures", True)
    report.checks.append(Check("runtime_oracle", "skip", "deferred to CI"))


def accept(
    candidate: Path,
    repo: Path,
    policy_path: Path | None = None,
    run: Runner = _run,
    soak: int = 1,
    static_only: bool = False,
) -> Report:
    """Run every applicable check and return the report."""
    policy_file = policy_path or repo / "agent" / "policy.toml"
    try:
        policy = load_policy(policy_file)
    except PolicyError as error:
        report = Report(str(candidate), "", "", "auto")
        _add(report, "policy", False, str(error))
        return report
    try:
        meta = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        report = Report(str(candidate), "", "", "auto")
        _add(report, "schema", False, f"cannot read candidate: {error}")
        return report
    if not isinstance(meta, dict):
        report = Report(str(candidate), "", "", "auto")
        _add(report, "schema", False, "candidate must be a JSON object")
        return report
    report = Report(str(candidate), _text(meta, "gap_type"), _text(meta, "artifact"), "auto")
    spec = _check_schema(report, meta, policy)
    if spec is None:
        return report
    report.acceptance = spec.acceptance
    _check_budget(report, repo, policy)
    if not _check_paths(report, repo, meta, spec):
        return report
    artifact = _artifact_path(repo, meta, spec)
    _check_duplicates(report, repo, artifact)
    if spec.acceptance == "human":
        _human(report, "human_decision", "artifact has no mechanical oracle")
        return report
    if static_only:
        _check_static_oracle(report, repo, meta, spec)
        return report
    if spec.oracle == "rule":
        _check_rule_text(report, artifact, meta)
        _check_rule(report, repo, meta, spec, run)
    elif spec.oracle == "pre_post":
        _check_pre_post(report, repo, meta, run, soak)
    elif spec.oracle == "fixture_command":
        _check_fixture_command(report, repo, meta, run)
    else:  # pragma: no cover - policy validation prevents this
        _human(report, "oracle", f"unknown oracle: {spec.oracle}")
    return report
