"""Unified local and CI gate runner for the polygate repository."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


@dataclass
class Stage:
    """One named gate stage with its command and working directory."""

    name: str
    cwd: Path
    command: list[str]


def _run(stage: Stage) -> bool:
    print(f"\n=== {stage.name} ===", flush=True)
    started = time.perf_counter()
    result = subprocess.run(stage.command, cwd=stage.cwd, check=False)
    elapsed = time.perf_counter() - started
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"--- {stage.name}: {status} ({elapsed:.1f}s)", flush=True)
    return result.returncode == 0


def backend_stages(with_mutation: bool, with_e2e: bool) -> list[Stage]:
    """Build backend gate stages."""
    stages = [
        Stage("backend lint", BACKEND, ["uv", "run", "ruff", "check", "src", "tests"]),
        Stage("backend format", BACKEND, ["uv", "run", "ruff", "format", "--check", "src", "tests"]),
        Stage("backend types", BACKEND, ["uv", "run", "mypy", "src"]),
        Stage("backend import boundaries", BACKEND, ["uv", "run", "lint-imports"]),
        Stage(
            "backend tests",
            BACKEND,
            [
                "uv",
                "run",
                "pytest",
                "tests",
                "--cov=polygate",
                "--cov-branch",
                "--cov-report=term",
                "--cov-report=lcov:lcov.info",
                "-q",
            ],
        ),
        Stage(
            "backend CRAP",
            BACKEND,
            ["uv", "run", "crap4py", "src", "--lcov", "lcov.info", "--max-crap", "6"],
        ),
        Stage("backend dead code", BACKEND, ["uv", "run", "vulture", "src", "--min-confidence", "80"]),
        Stage("backend docstrings", BACKEND, ["uv", "run", "interrogate", "-q", "src"]),
        Stage("backend cognitive complexity", BACKEND, ["uv", "run", "flake8", "src"]),
        Stage("backend security", BACKEND, ["uv", "run", "bandit", "-q", "-c", ".bandit", "-r", "src"]),
        Stage(
            "backend deps export",
            BACKEND,
            ["uv", "export", "--no-dev", "--format", "requirements-txt", "--no-hashes", "-o", ".runtime-reqs.txt"],
        ),
        Stage("backend deps", BACKEND, ["uv", "run", "pip-audit", "-r", ".runtime-reqs.txt"]),
        Stage("backend dependency hygiene", BACKEND, ["uv", "run", "deptry", "src"]),
        Stage(
            "backend design rules",
            ROOT,
            [
                "uv",
                "run",
                "--project",
                "backend",
                "semgrep",
                "scan",
                "--config",
                "rules/architecture.yml",
                "--error",
                "--quiet",
                "backend/src",
                "frontend/src",
            ],
        ),
        Stage("backend structural rules", ROOT, ["ast-grep", "scan", "--config", "sgconfig.yml"]),
    ]
    if with_e2e:
        stages.append(Stage("backend e2e", BACKEND, ["uv", "run", "pytest", "tests/e2e", "-q", "-m", "e2e"]))
        stages.append(
            Stage("backend contracts", BACKEND, ["uv", "run", "pytest", "tests/e2e/test_contracts.py", "-q", "-m", "contract"])
        )
    if with_mutation:
        stages.append(Stage("backend mutation", BACKEND, [sys.executable, str(ROOT / "scripts/mutation_gate.py"), "75"]))
    return stages


def frontend_stages(with_mutation: bool) -> list[Stage]:
    """Build frontend gate stages."""
    stages = [
        Stage("frontend lint", FRONTEND, ["pnpm", "run", "lint"]),
        Stage("frontend format", FRONTEND, ["pnpm", "run", "format:check"]),
        Stage("frontend types", FRONTEND, ["pnpm", "run", "typecheck"]),
        Stage(
            "frontend dependency boundaries",
            FRONTEND,
            ["./node_modules/.bin/dependency-cruise", "src", "tests", "--config", ".dependency-cruiser.cjs"],
        ),
        Stage("frontend tests", FRONTEND, ["pnpm", "run", "test"]),
        Stage("frontend CRAP report", FRONTEND, ["pnpm", "run", "crap"]),
        Stage(
            "frontend CRAP",
            FRONTEND,
            [sys.executable, str(ROOT / "scripts/crap_js_gate.py"), "crap-report/crap-report.json", "6"],
        ),
        Stage(
            "frontend dead code",
            FRONTEND,
            ["./node_modules/.bin/knip", "--include", "files,exports,types,dependencies,devDependencies,unlisted"],
        ),
    ]
    if with_mutation:
        stages.append(Stage("frontend mutation", FRONTEND, ["pnpm", "run", "mutate"]))
    return stages


def duplication_stage() -> Stage:
    """Build the cross-language duplicate-code gate."""
    return Stage(
        "duplicates",
        ROOT,
        ["uv", "run", "--project", "backend", "--with", "jscpd", "jscpd", "backend/src", "frontend/src"],
    )


def cohesion_stage() -> Stage:
    """Build the LCOM cohesion gate."""
    return Stage("cohesion", ROOT, [sys.executable, str(ROOT / "scripts/cohesion_gate.py")])


def size_stage() -> Stage:
    """Build the module size gate."""
    return Stage("module size", ROOT, [sys.executable, str(ROOT / "scripts/size_gate.py")])


def docs_stage() -> Stage:
    """Build the documentation gate."""
    return Stage("docs", ROOT, [sys.executable, str(ROOT / "scripts/docs_gate.py")])


def main(argv: list[str]) -> int:
    """Run requested gate groups and report the overall result."""
    parser = argparse.ArgumentParser(description="Run polygate quality gates")
    parser.add_argument("--backend", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--docs", action="store_true")
    parser.add_argument("--mutation", action="store_true", help="add mutation testing (slow)")
    parser.add_argument("--e2e", action="store_true", help="add end-to-end tests")
    parser.add_argument("--all", action="store_true", help="backend, frontend, docs")
    options = parser.parse_args(argv[1:])

    run_backend = options.backend or options.all or not (options.frontend or options.docs)
    run_frontend = options.frontend or options.all
    run_docs = options.docs or options.all

    stages: list[Stage] = []
    if run_backend:
        stages += backend_stages(options.mutation, options.e2e)
    if run_frontend:
        stages += frontend_stages(options.mutation)
    stages.append(size_stage())
    stages.append(cohesion_stage())
    stages.append(duplication_stage())
    if run_docs:
        stages.append(docs_stage())

    results = [(stage.name, _run(stage)) for stage in stages]
    print("\n=== gate summary ===")
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    failed = [name for name, passed in results if not passed]
    if failed:
        print(f"\n{len(failed)} gate(s) failed", file=sys.stderr)
        return 1
    print("\nall gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
