"""CLI entry point for accepting or rejecting an agent gate candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_gate.accept import accept


def main(argv: list[str]) -> int:
    """Run the acceptance checks and return the exit code."""
    parser = argparse.ArgumentParser(description="Accept or reject an agent gate candidate")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--repo", default=Path(), type=Path)
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--soak", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args(argv[1:])
    report = accept(options.candidate, options.repo.resolve(), options.policy, soak=options.soak)
    if options.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"candidate {report.candidate}: {report.verdict}")
        for check in report.checks:
            print(f"  {check.status:12} {check.name}: {check.detail}")
    return {"pass": 0, "fail": 1, "needs_human": 2}[report.verdict]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
