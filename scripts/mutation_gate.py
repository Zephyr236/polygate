"""Parse mutmut results and enforce the mutation score gate."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter

STATUSES = ("killed", "survived", "timeout", "skipped", "no tests", "not checked")


def parse_results(output: str) -> Counter[str]:
    """Count mutant outcomes from ``mutmut results`` output."""
    counts: Counter[str] = Counter()
    for line in output.splitlines():
        stripped = line.strip()
        status = stripped.rsplit(":", 1)[-1].strip() if ":" in stripped else "unknown"
        counts[status] += 1
    return counts


def mutation_score(counts: Counter[str]) -> float:
    """Return killed mutants as a share of killed plus survived mutants."""
    scored = counts["killed"] + counts["survived"]
    if scored == 0:
        return 0.0
    return counts["killed"] / scored * 100


def main(argv: list[str]) -> int:
    """Run mutmut results and fail when the score is below the threshold."""
    threshold = float(argv[1]) if len(argv) > 1 else 75.0
    output = subprocess.run(
        ["uv", "run", "mutmut", "results", "--all", "true"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    counts = parse_results(output)
    score = mutation_score(counts)
    print(f"mutation score: {score:.2f}% (threshold {threshold:.2f}%)")
    print("  " + ", ".join(f"{status}={count}" for status, count in counts.most_common()))
    if score < threshold:
        print("FAIL: mutation score below threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
