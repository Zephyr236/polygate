"""Map the existing static rules onto source files and list uncovered modules."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Any

SOURCE_PATTERNS = ("backend/src/**/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx")


def source_files(repo: Path) -> list[str]:
    """Return repo-relative source files covered by the static gate suite."""
    files: set[str] = set()
    for pattern in SOURCE_PATTERNS:
        files.update(str(path.relative_to(repo)) for path in repo.glob(pattern) if path.is_file())
    return sorted(files)


def _parse_list_section(lines: list[str], start: int, key: str) -> tuple[list[str], int]:
    values: list[str] = []
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if stripped.startswith("- "):
            values.append(stripped[2:].strip().strip("\"'"))
            index += 1
            continue
        break
    del key
    return values, index


def parse_semgrep(text: str) -> list[dict[str, Any]]:
    """Extract rule ids plus include/exclude path lists from a semgrep rules file."""
    rules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section: str | None = None
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("- id:"):
            current = {"id": stripped.split(":", 1)[1].strip().strip("\"'"), "include": [], "exclude": []}
            rules.append(current)
            section = None
        elif current is not None and stripped in {"include:", "exclude:"}:
            section = stripped[:-1]
            values, index = _parse_list_section(lines, index, section)
            current[section].extend(values)
            continue
        elif stripped and not lines[index].startswith((" ", "\t")) and stripped != "---":
            section = None
        index += 1
    return rules


def parse_ast_grep(text: str) -> dict[str, Any]:
    """Extract id, files and ignores from a single ast-grep rule file."""
    rule: dict[str, Any] = {"id": "unknown", "include": [], "exclude": []}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("id:"):
            rule["id"] = stripped.split(":", 1)[1].strip().strip("\"'")
        elif stripped in {"files:", "ignores:"}:
            key = "include" if stripped == "files:" else "exclude"
            values, index = _parse_list_section(lines, index, key)
            rule[key].extend(values)
            continue
        index += 1
    return rule


def _glob_variants(pattern: str) -> list[str]:
    variants = [pattern]
    if "**/" in pattern:
        variants.append(pattern.replace("**/", ""))
    return variants


def _matches(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if any(fnmatch.fnmatch(path, variant) for variant in _glob_variants(pattern)):
            return True
        prefix = pattern.rstrip("/")
        if not any(char in pattern for char in "*?[") and (path == prefix or path.startswith(prefix + "/")):
            return True
    return False


def applies(rule: dict[str, Any], path: str) -> bool:
    """Return whether a rule's include/exclude patterns cover a file."""
    includes = rule.get("include") or []
    excludes = rule.get("exclude") or []
    if excludes and _matches(path, excludes):
        return False
    if not includes:
        return True
    return _matches(path, includes)


def build_map(repo: Path) -> dict[str, Any]:
    """Build the rule coverage document."""
    files = source_files(repo)
    rules: list[dict[str, Any]] = []
    semgrep = repo / "rules" / "architecture.yml"
    if semgrep.is_file():
        for rule in parse_semgrep(semgrep.read_text(encoding="utf-8")):
            rules.append({**rule, "tool": "semgrep", "file": "rules/architecture.yml"})
    for path in sorted((repo / "rules" / "ast-grep").glob("*.yml")):
        parsed = parse_ast_grep(path.read_text(encoding="utf-8"))
        rules.append({**parsed, "tool": "ast-grep", "file": str(path.relative_to(repo))})
    coverage = {path: [] for path in files}
    for rule in rules:
        matched = [path for path in files if applies(rule, path)]
        rule["matched"] = len(matched)
        for path in matched:
            coverage[path].append(rule["id"])
    uncovered = sorted(path for path, ids in coverage.items() if not ids)
    return {
        "rule_count": len(rules),
        "source_count": len(files),
        "rules": rules,
        "modules": coverage,
        "uncovered": uncovered,
    }


def render_markdown(document: dict[str, Any]) -> str:
    """Render a compact markdown summary for humans and agents."""
    lines = [
        "# Rule coverage",
        "",
        f"Rules: {document['rule_count']} · source files: {document['source_count']}",
        "",
        "## Rules",
        "",
        "| Rule | Tool | Matched files |",
        "| --- | --- | --- |",
    ]
    lines += [f"| `{rule['id']}` | {rule['tool']} | {rule['matched']} |" for rule in document["rules"]]
    lines += ["", "## Modules with no rule", ""]
    lines += [f"- `{path}`" for path in document["uncovered"]] or ["- none"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    """Write the coverage JSON and optional markdown summary."""
    parser = argparse.ArgumentParser(description="Map static rules onto source files")
    parser.add_argument("--repo", type=Path, default=Path())
    parser.add_argument("--json", type=Path, default=Path("reports/rule-coverage.json"))
    parser.add_argument("--markdown", type=Path, default=None)
    options = parser.parse_args(argv[1:])
    repo = options.repo.resolve()
    document = build_map(repo)
    options.json.parent.mkdir(parents=True, exist_ok=True)
    options.json.write_text(json.dumps(document, indent=2), encoding="utf-8")
    if options.markdown is not None:
        options.markdown.parent.mkdir(parents=True, exist_ok=True)
        options.markdown.write_text(render_markdown(document), encoding="utf-8")
    print(
        f"rules={document['rule_count']} source={document['source_count']} uncovered={len(document['uncovered'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
