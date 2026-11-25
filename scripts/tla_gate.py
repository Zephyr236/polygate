"""Run the TLA+ gate state-machine model with TLC."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

JAR_URL = "https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar"


def ensure_jar(path: Path) -> Path:
    """Download the pinned TLA+ tools jar when it is absent."""
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(JAR_URL, timeout=120) as response:
        path.write_bytes(response.read())
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Model-check the design gate")
    parser.add_argument("--jar", type=Path, default=Path(".cache/tla2tools.jar"))
    parser.add_argument("--spec", type=Path, default=Path("specs/tla/gate.tla"))
    parser.add_argument("--config", type=Path, default=Path("specs/tla/gate.cfg"))
    options = parser.parse_args()
    jar = ensure_jar(options.jar)
    with tempfile.TemporaryDirectory() as metadir:
        result = subprocess.run(
            [
                "java",
                "-cp",
                str(jar),
                "tlc2.TLC",
                "-config",
                str(options.config),
                "-metadir",
                metadir,
                "-deadlock",
                str(options.spec),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    print(result.stdout[-4000:])
    print(result.stderr[-2000:], file=sys.stderr)
    if result.returncode != 0:
        return result.returncode
    if "No error has been found" not in result.stdout:
        print("TLC did not report a clean model check", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
