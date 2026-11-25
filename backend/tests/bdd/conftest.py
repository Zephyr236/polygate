"""Keep Gherkin tags as acceptance metadata, not pytest markers."""

from __future__ import annotations

from typing import Any


def pytest_bdd_apply_tag(tag: str, function: Any) -> bool:
    """Consume feature tags; contract_gate.py reads them from the feature files."""
    del tag, function
    return True
