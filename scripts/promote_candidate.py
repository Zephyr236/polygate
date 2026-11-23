"""CLI entry point for promoting an accepted agent candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_gate.promote import PromoteError, promote


def main(argv: list[str]) -> int:
    """Promote a candidate and print the registry entry."""
    parser = argparse.ArgumentParser(description="Promote an accepted agent candidate")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repo", default=".", type=Path)
    parser.add_argument("--issue", default="")
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args(argv[1:])
    try:
        entry = promote(
            options.candidate,
            options.report,
            options.repo.resolve(),
            options.issue,
            options.policy,
        )
    except PromoteError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if options.json:
        print(json.dumps(entry, indent=2, ensure_ascii=False))
    else:
        print(f"promoted {entry['id']} -> {entry['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
