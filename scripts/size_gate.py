"""Enforce module size limits so logic is split by responsibility, not relocated."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# file (line) limits keep modules readable; function (line) limits stop mega-functions.
LIMITS = {
    "backend_file": 320,
    "backend_function": 60,
    "backend_module_lines": 60,
    "frontend_file": 320,
    "frontend_function": 70,
    "frontend_module_lines": 60,
}


@dataclass
class Finding:
    """One size violation with its measured value."""

    path: str
    kind: str
    measured: int
    limit: int


def python_files() -> list[Path]:
    """Return backend source modules."""
    return sorted((ROOT / "backend" / "src" / "polygate").rglob("*.py"))


TYPE_ONLY = ("src/api/types.ts", "src/vite-env.d.ts")


def frontend_files() -> list[Path]:
    """Return frontend source modules, excluding pure type declaration files."""
    base = ROOT / "frontend" / "src"
    return sorted(path for path in base.rglob("*") if path.suffix in {".ts", ".tsx"} and not _type_only(path))


def _type_only(path: Path) -> bool:
    """Report whether a file only declares interfaces."""
    text = path.read_text(encoding="utf-8")
    return path.name == "types.ts" or ("interface " in text and "function " not in text and "=>" not in text)


def check_file_lengths(files: list[Path], limit: int, label: str) -> list[Finding]:
    """Return files exceeding the line limit."""
    findings: list[Finding] = []
    for path in files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > limit:
            findings.append(Finding(str(path.relative_to(ROOT)), f"{label} file lines", lines, limit))
    return findings


def python_functions(path: Path) -> list[tuple[str, int]]:
    """Return (qualified name, line count) for each top-level-ish function."""
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    rows: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            rows.append((node.name, end - node.lineno + 1))
    return rows


def check_python_functions(files: list[Path], limit: int) -> list[Finding]:
    """Return Python functions exceeding the line limit."""
    findings: list[Finding] = []
    for path in files:
        for name, length in python_functions(path):
            if length > limit:
                findings.append(Finding(f"{path.relative_to(ROOT)}::{name}", "function lines", length, limit))
    return findings


def check_frontend_functions(files: list[Path], limit: int) -> list[Finding]:
    """Return TypeScript functions exceeding the approximate line limit."""
    findings: list[Finding] = []
    for path in files:
        if "types" in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        for name, body in _ts_function_spans(text):
            if body > limit:
                findings.append(Finding(f"{path.relative_to(ROOT)}::{name}", "function lines", body, limit))
    return findings


def _ts_function_spans(text: str) -> list[tuple[str, int]]:
    """Return approximate (name, line span) pairs for function declarations."""
    import re

    spans: list[tuple[str, int]] = []
    pattern = re.compile(r"^(?:export )?(?:async )?function (\w+)", re.MULTILINE)
    for match in pattern.finditer(text):
        start = text[: match.start()].count("\n")
        end = _block_end(text, match.end())
        spans.append((match.group(1), end - start + 1))
    return spans


def _block_end(text: str, offset: int) -> int:
    """Compute the line of a declaration's closing brace."""
    depth = 0
    started = False
    line = text[:offset].count("\n")
    for char in text[offset:]:
        if char == "\n":
            line += 1
        if char == "{":
            depth += 1
            started = True
        elif char == "}":
            depth -= 1
            if started and depth == 0:
                return line
    return line


def check_module_line_ratio(files: list[Path], limit: int, label: str) -> list[Finding]:
    """Return modules whose total lines exceed the limit multiplied by their function count."""
    del label
    findings: list[Finding] = []
    for path in files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines <= 0:
            continue
        if path.suffix == ".py":
            count = max(len(python_functions(path)), 1)
        else:
            count = max(len(_ts_function_spans(path.read_text(encoding="utf-8"))), 1)
        allowed = count * limit
        if lines > allowed:
            findings.append(Finding(str(path.relative_to(ROOT)), "module lines", lines, allowed))
    return findings


def main(argv: list[str]) -> int:
    """Report every size violation and fail when any limit is exceeded."""
    parser = argparse.ArgumentParser(description="Module size gate")
    parser.parse_args(argv[1:])

    backend_sources = python_files()
    frontend_sources = frontend_files()
    findings = [
        *check_file_lengths(backend_sources, LIMITS["backend_file"], "backend"),
        *check_file_lengths(frontend_sources, LIMITS["frontend_file"], "frontend"),
        *check_python_functions(backend_sources, LIMITS["backend_function"]),
        *check_frontend_functions(frontend_sources, LIMITS["frontend_function"]),
        *check_module_line_ratio(backend_sources, LIMITS["backend_module_lines"], "backend"),
        *check_module_line_ratio(frontend_sources, LIMITS["frontend_module_lines"], "frontend"),
    ]
    for finding in findings:
        print(f"FAIL {finding.path}: {finding.kind} {finding.measured} > {finding.limit}")
    if findings:
        print(f"{len(findings)} size violation(s)", file=sys.stderr)
        return 1
    print("size gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
