"""Tests for the architecture metrics and ratchet."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
METRICS = Path(REPO / "scripts" / "architecture_metrics.py")
SPEC = importlib.util.spec_from_file_location("architecture_metrics", METRICS)
assert SPEC and SPEC.loader
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


def test_cycle_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "src" / "pkg"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (source / "b.py").write_text("from pkg import a\n", encoding="utf-8")
    result = metrics.metrics(tmp_path)
    assert result["python"]["cycles"] == [["pkg.a", "pkg.b"]]


def test_metrics_report_largest_file(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "src" / "pkg"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "large.py").write_text("x = 1\n" * 20, encoding="utf-8")
    result = metrics.metrics(tmp_path)
    assert result["python"]["max_file"]["lines"] == 20
