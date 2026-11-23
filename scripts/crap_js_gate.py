"""Enforce a per-function CRAP threshold on the crap-score JSON report."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def iter_functions(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten one file entry into function rows."""
    rows: list[dict[str, Any]] = []
    for path_key, entry in document.items():
        source = entry.get("source", path_key) if isinstance(entry, dict) and "source" in entry else path_key
        functions = entry.get("functions", entry) if isinstance(entry, dict) else {}
        if not isinstance(functions, dict):
            continue
        for name, function in functions.items():
            if not isinstance(function, dict):
                continue
            rows.append(
                {
                    "file": source,
                    "name": name,
                    "complexity": function.get("complexity", 1),
                    "coverage": (function.get("statements") or {}).get("coverage", 1),
                    "crap": (function.get("statements") or {}).get("crap", 1),
                }
            )
    return rows


def violations(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    """Return rows whose CRAP score exceeds the threshold."""
    return [row for row in rows if float(row["crap"]) > threshold]


def main(argv: list[str]) -> int:
    """Read a crap-score JSON report and fail when any function exceeds the limit."""
    report = Path(argv[1] if len(argv) > 1 else "crap-report/crap-report.json")
    threshold = float(argv[2]) if len(argv) > 2 else 6.0
    if not report.exists():
        print(f"missing CRAP report: {report}", file=sys.stderr)
        return 1
    document = json.loads(report.read_text(encoding="utf-8"))
    rows = iter_functions(document)
    bad = violations(rows, threshold)
    worst = sorted(rows, key=lambda row: float(row["crap"]), reverse=True)[:5]
    print(f"functions checked: {len(rows)} | CRAP threshold: {threshold}")
    for row in worst:
        print(f"  {row['crap']:>6.2f} {row['name']} ({row['file']}) cc={row['complexity']}")
    if bad:
        print(f"FAIL: {len(bad)} function(s) exceed CRAP {threshold}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
