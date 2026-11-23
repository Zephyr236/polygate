"""LCOM cohesion gate: measures only classes that define behaviour."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "backend" / "src" / "polygate"
MIN_METHODS = 3
MIN_COHESION = 0.5


@dataclass(frozen=True)
class Cohesion:
    """One class with its LCOM4 cohesion value."""

    path: str
    name: str
    methods: int
    value: float


def _attributes(node: ast.AST) -> set[str]:
    """Return the ``self.<attr>`` names referenced inside a node."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            if child.value.id in {"self", "cls"}:
                names.add(child.attr)
    return names


def _calls_methods(node: ast.AST, methods: set[str]) -> set[str]:
    """Return the names of sibling methods invoked from a node."""
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr in methods
    }


def _is_abstract(node: ast.ClassDef) -> bool:
    """Report whether a class declares abstract methods."""
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in item.decorator_list:
            name = decorator.attr if isinstance(decorator, ast.Attribute) else getattr(decorator, "id", "")
            if name == "abstractmethod":
                return True
    return False


def class_cohesion(node: ast.ClassDef) -> Cohesion | None:
    """Compute LCOM4 as connected components over shared attributes and calls."""
    methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    method_names = {method.name for method in methods}
    if len(methods) < MIN_METHODS or _is_abstract(node):
        return None
    links: list[set[int]] = []
    for index, method in enumerate(methods):
        neighbours: set[int] = set()
        owned = _attributes(method)
        called = _calls_methods(method, method_names)
        for other_index, other in enumerate(methods):
            if other_index == index:
                continue
            if owned & _attributes(other):
                neighbours.add(other_index)
            if other.name in called or method.name in _calls_methods(other, method_names):
                neighbours.add(other_index)
        links.append(neighbours | {index})
    components = _components(links)
    return Cohesion(
        path="",
        name=node.name,
        methods=len(methods),
        value=1.0 / components,
    )


def _components(links: list[set[int]]) -> int:
    """Count connected components in an undirected adjacency list."""
    seen: set[int] = set()
    count = 0
    for start in range(len(links)):
        if start in seen:
            continue
        count += 1
        stack = [start]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(links[current] - seen)
    return count


def collect() -> list[Cohesion]:
    """Scan the backend package and return cohesion for behaviour-carrying classes."""
    results: list[Cohesion] = []
    for path in sorted(SOURCE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            measured = class_cohesion(node)
            if measured is None:
                continue
            results.append(
                Cohesion(
                    path=str(path.relative_to(ROOT)),
                    name=measured.name,
                    methods=measured.methods,
                    value=measured.value,
                )
            )
    return results


def main() -> int:
    """Report low-cohesion classes and fail when any fall below the threshold."""
    measurements = collect()
    low = [item for item in measurements if item.value < MIN_COHESION]
    print(f"classes measured: {len(measurements)} | threshold: LCOM4 ≥ {MIN_COHESION}")
    for item in sorted(measurements, key=lambda entry: entry.value)[:8]:
        print(f"  {item.value:>5.2f} {item.name} ({item.methods} methods, {item.path})")
    for item in low:
        print(f"FAIL {item.name} in {item.path}: cohesion {item.value:.2f} < {MIN_COHESION}", file=sys.stderr)
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
