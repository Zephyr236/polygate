"""Run the full acceptance-contract check locally and in CI."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path) -> int:
    """Run one command and stream it."""
    print(f"\n$ {' '.join(command)}  ({cwd.relative_to(ROOT)})", flush=True)
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main() -> int:
    steps = [
        (
            [
                str(BACKEND / ".venv" / "bin" / "python"),
                "scripts/contract_gate.py",
                "--junit",
                str(BACKEND / "bdd.xml"),
            ],
            ROOT,
        ),
        ([str(BACKEND / ".venv" / "bin" / "python"), "scripts/adr_gate.py"], ROOT),
        ([str(BACKEND / ".venv" / "bin" / "python"), "scripts/capability_gate.py"], ROOT),
        ([str(BACKEND / ".venv" / "bin" / "python"), "scripts/architecture_gate.py"], ROOT),
        ([str(BACKEND / ".venv" / "bin" / "python"), "scripts/tla_gate.py"], ROOT),
        (["pnpm", "run", "gherkin:lint"], FRONTEND),
        (["pnpm", "run", "bdd"], FRONTEND),
        (["pnpm", "run", "openspec:validate"], FRONTEND),
    ]
    bdd = run(
        [
            str(BACKEND / ".venv" / "bin" / "python"),
            "-m",
            "pytest",
            "tests/bdd",
            f"--junitxml={BACKEND / 'bdd.xml'}",
            "-q",
        ],
        BACKEND,
    )
    if bdd:
        return bdd
    for command, cwd in steps:
        if run(command, cwd):
            return 1
    print("\nacceptance contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
