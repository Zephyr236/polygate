"""Shared fixtures."""

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Ensure mutation runs surface every test module to the worker."""
    del config, items
