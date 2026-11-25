"""Validate MADR ADR structure and requirement references."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

REQUIRED = ["## Context", "## Decision", "## Consequences"]
STATUS = re.compile(r"^- Status:\s*(.+)$", re.MULTILINE)
REQUIREMENTS = re.compile(r"^- Requirements:\s*(.+)$", re.MULTILINE)
SUPERSEDES = re.compile(r"\((\d{4}-[a-z0-9-]+\.md)\)")


def check(adr_dir: Path, requirements_path: Path) -> list[str]:
    """Return ADR problems."""
    requirements = yaml.safe_load(requirements_path.read_text(encoding="utf-8"))["requirements"]
    ids = set(requirements)
    problems: list[str] = []
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        missing = [section for section in REQUIRED if section not in text]
        if missing:
            problems.append(f"{path.name}: missing {', '.join(missing)}")
        status = STATUS.search(text)
        if not status:
            problems.append(f"{path.name}: missing Status")
        elif status.group(1).split()[0].lower() not in {
            "accepted",
            "proposed",
            "provisional",
            "superseded",
            "rejected",
        }:
            problems.append(f"{path.name}: invalid status {status.group(1)!r}")
        refs = REQUIREMENTS.search(text)
        if refs:
            for rid in [item.strip() for item in refs.group(1).split(",") if item.strip()]:
                if rid not in ids:
                    problems.append(f"{path.name}: unknown requirement {rid}")
        for target in SUPERSEDES.findall(text):
            if not (adr_dir / target).exists():
                problems.append(f"{path.name}: missing superseded ADR {target}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ADRs")
    parser.add_argument("--adr-dir", type=Path, default=Path("docs/adr"))
    parser.add_argument("--requirements", type=Path, default=Path("specs/requirements.yaml"))
    options = parser.parse_args()
    problems = check(options.adr_dir, options.requirements)
    if problems:
        print("\n".join(problems))
        return 1
    print("ADR contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
