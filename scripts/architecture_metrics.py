"""Compute architecture metrics for the Python and frontend import graphs."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

IMPORT = re.compile(r"""from\s+["'](\.[^"']+)["']""")
TS_EXT = {".ts", ".tsx", ".js", ".jsx"}


def _python_modules(root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    source = root / "backend" / "src"
    for path in source.rglob("*.py"):
        relative = path.relative_to(source).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path
    return modules


def _python_edges(modules: dict[str, Path]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [
                    f"{node.module}.{alias.name}" if f"{node.module}.{alias.name}" in modules else node.module
                    for alias in node.names
                ]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                target = (
                    name
                    if name in modules
                    else next(
                        (candidate for candidate in modules if name.startswith(candidate + ".")),
                        None,
                    )
                )
                if target and target != module:
                    edges.add((module, target))
    return edges


def _cycles(nodes: set[str], edges: set[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, list[str]] = {node: [] for node in nodes}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in indices:
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
            elif neighbor in on_stack:
                low[node] = min(low[node], indices[neighbor])
        if low[node] == indices[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.discard(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1:
                result.append(sorted(component))

    for node in nodes:
        if node not in indices:
            visit(node)
    return sorted(result)


def _frontend_metrics(root: Path) -> dict[str, Any]:
    source = root / "frontend" / "src"
    modules = {str(path.relative_to(source)): path for path in source.rglob("*") if path.suffix in TS_EXT}
    edges: set[tuple[str, str]] = set()
    for module, path in modules.items():
        for match in IMPORT.finditer(path.read_text(encoding="utf-8")):
            target_path = (path.parent / match.group(1)).resolve()
            for suffix in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"):
                candidate = Path(str(target_path) + suffix)
                if candidate.exists():
                    target = str(candidate.relative_to(source))
                    if target != module:
                        edges.add((module, target))
                    break
    return {
        "files": len(modules),
        "lines": sum(len(path.read_text(encoding="utf-8").splitlines()) for path in modules.values()),
        "imports": len(edges),
        "cycles": _cycles(set(modules), edges),
    }


def metrics(root: Path) -> dict[str, Any]:
    """Return line, import and cycle metrics for the repository."""
    modules = _python_modules(root)
    edges = _python_edges(modules)
    file_lines = {
        str(path.relative_to(root)): len(path.read_text(encoding="utf-8").splitlines())
        for path in modules.values()
    }
    largest = max(file_lines.items(), key=lambda item: item[1], default=("", 0))
    return {
        "python": {
            "files": len(modules),
            "lines": sum(file_lines.values()),
            "max_file": {"path": largest[0], "lines": largest[1]},
            "imports": len(edges),
            "cycles": _cycles(set(modules), edges),
        },
        "frontend": _frontend_metrics(root),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Architecture metrics")
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument("--out", type=Path)
    options = parser.parse_args()
    result = metrics(options.root.resolve())
    text = json.dumps(result, indent=2) + "\n"
    if options.out:
        options.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
