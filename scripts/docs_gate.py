"""Documentation gate: required files, config-doc parity, links and AGENTS sections."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = [
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "docs/index.md",
    "docs/architecture.md",
    "docs/routing.md",
    "docs/providers.md",
    "docs/metrics.md",
    "docs/operations.md",
    "docs/gates.md",
    "docs/frontend.md",
    "docs/api.md",
    "docs/config-reference.md",
]
AGENT_SECTIONS = [
    "## Project layout",
    "## Invariants",
    "## How to run gates",
    "## Adding a provider",
    "## Where to change what",
]
CONFIG_FIELDS_DOC = ROOT / "docs/config-reference.md"
CONFIG_MODULE = ROOT / "backend/src/polygate/config.py"


def missing_files() -> list[str]:
    """Return required documents that do not exist."""
    return [name for name in REQUIRED_DOCS if not (ROOT / name).is_file()]


def config_fields() -> list[str]:
    """Extract provider and routing field names from the pydantic models."""
    text = CONFIG_MODULE.read_text(encoding="utf-8")
    fields: list[str] = []
    for block in ("ProviderConfig", "RoutingConfig", "RoutingWeights", "RetryPolicy", "Timeouts", "TimeWindow"):
        match = re.search(rf"class {block}\(BaseModel\):(.*?)\n\n\nclass ", text, re.S)
        body = match.group(1) if match else ""
        fields.extend(re.findall(r"\n    ([\w_]+):\s", body))
    return fields


def undocumented_fields() -> list[str]:
    """Return provider/routing fields absent from the generated reference page."""
    if not CONFIG_FIELDS_DOC.is_file():
        return config_fields()
    documented = CONFIG_FIELDS_DOC.read_text(encoding="utf-8")
    return [field for field in config_fields() if f"`{field}`" not in documented and field not in documented]


def agents_sections_missing() -> list[str]:
    """Return required AGENTS.md sections that are absent."""
    path = ROOT / "AGENTS.md"
    if not path.is_file():
        return AGENT_SECTIONS
    text = path.read_text(encoding="utf-8")
    return [section for section in AGENT_SECTIONS if section not in text]


def relative_links_missing() -> list[str]:
    """Return documented relative paths that do not resolve."""
    broken: list[str] = []
    for md in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        if not md.is_file():
            continue
        for target in re.findall(r"\]\(([^)#]+\.md[^)]*)\)", md.read_text(encoding="utf-8")):
            resolved = (md.parent / target.split("#")[0]).resolve()
            if not resolved.is_file():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    return broken


def gate_targets() -> set[str]:
    """Return stage names exposed by scripts/gate.py."""
    text = (ROOT / "scripts/gate.py").read_text(encoding="utf-8")
    return set(re.findall(r'Stage\("([^"]+)"', text))


def readme_targets() -> set[str]:
    """Return gate names mentioned in the README gate table."""
    path = ROOT / "README.md"
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8").lower()
    return {name for name in gate_targets() if name.lower() in text}


def openapi_check() -> list[str]:
    """Regenerate the OpenAPI document and verify it parses."""
    problems: list[str] = []
    try:
        output = subprocess.run(
            ["uv", "run", "python", "-c", "from polygate.app import create_app; import json; print(json.dumps(create_app().openapi()))"],
            cwd=ROOT / "backend",
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:  # pragma: no cover - tooling missing
        return [f"cannot run openapi export: {error}"]
    if output.returncode != 0:
        return [f"openapi export failed: {output.stderr.strip()[:200]}"]
    try:
        json.loads(output.stdout)
    except json.JSONDecodeError:
        problems.append("openapi export is not valid JSON")
    return problems


def main() -> int:
    """Run every documentation check and report failures."""
    checks = {
        "required docs present": missing_files(),
        "AGENTS sections": agents_sections_missing(),
        "config reference coverage": undocumented_fields(),
        "internal links": relative_links_missing(),
        "README gate names": sorted(gate_targets() - readme_targets()),
        "openapi": openapi_check(),
    }
    failed = False
    for name, problems in checks.items():
        if problems:
            failed = True
            print(f"FAIL {name}:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"PASS {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
