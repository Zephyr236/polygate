"""Fail when architecture metrics regress beyond the committed baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture_metrics


def _regressions(current: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for language in ("python", "frontend"):
        now = current.get(language, {})
        was = baseline.get(language, {})
        if now.get("max_file", {}).get("lines", 0) > was.get("max_file", {}).get("lines", 0):
            problems.append(
                f"{language}: max file lines {now['max_file']} exceeds baseline {was['max_file']}"
            )
        if len(now.get("cycles", [])) > len(was.get("cycles", [])):
            problems.append(f"{language}: new dependency cycles: {now.get('cycles')}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Architecture ratchet")
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument("--baseline", type=Path, default=Path("specs/architecture-baseline.json"))
    parser.add_argument("--update", action="store_true")
    options = parser.parse_args()
    current = architecture_metrics.metrics(options.root.resolve())
    if options.update or not options.baseline.exists():
        options.baseline.parent.mkdir(parents=True, exist_ok=True)
        options.baseline.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"architecture baseline written: {options.baseline}")
        return 0
    baseline = json.loads(options.baseline.read_text(encoding="utf-8"))
    problems = _regressions(current, baseline)
    if problems:
        print("\n".join(problems))
        return 1
    print("architecture ratchet passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
