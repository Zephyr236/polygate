"""Tests for the rule coverage map."""

from __future__ import annotations

from pathlib import Path

from rule_coverage import build_map, parse_ast_grep, parse_semgrep


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "rules" / "ast-grep").mkdir(parents=True)
    (tmp_path / "backend" / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "backend" / "src" / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "backend" / "src" / "pkg" / "b.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "ui.ts").write_text("export const a = 1;\n", encoding="utf-8")
    (tmp_path / "rules" / "architecture.yml").write_text(
        "rules:\n"
        "  - id: only-a\n"
        "    languages: [python]\n"
        "    severity: ERROR\n"
        "    message: a\n"
        "    paths:\n"
        "      include:\n"
        "        - backend/src/pkg/a.py\n"
        "    pattern: x = ...\n",
        encoding="utf-8",
    )
    (tmp_path / "rules" / "ast-grep" / "frontend.yml").write_text(
        "id: frontend-only\nfiles:\n  - frontend/src/**/*.ts\nrule:\n  pattern: a\n",
        encoding="utf-8",
    )
    return tmp_path


def test_parse_semgrep_paths() -> None:
    rules = parse_semgrep(
        "rules:\n  - id: r\n    paths:\n      include:\n        - backend/src/x\n"
        "      exclude:\n        - backend/src/x/skip.py\n"
    )
    assert rules[0]["id"] == "r"
    assert rules[0]["include"] == ["backend/src/x"]
    assert rules[0]["exclude"] == ["backend/src/x/skip.py"]


def test_parse_ast_grep_files() -> None:
    rule = parse_ast_grep("id: r2\nfiles:\n  - frontend/src/**/*.ts\nignores:\n  - frontend/src/vendor/**\n")
    assert rule["include"] == ["frontend/src/**/*.ts"]
    assert rule["exclude"] == ["frontend/src/vendor/**"]


def test_build_map_marks_uncovered_modules(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    document = build_map(repo)
    assert document["rule_count"] == 2
    assert "backend/src/pkg/a.py" in document["modules"]
    assert document["modules"]["backend/src/pkg/a.py"] == ["only-a"]
    assert document["modules"]["frontend/src/ui.ts"] == ["frontend-only"]
    assert document["uncovered"] == ["backend/src/pkg/b.py"]


def test_directory_prefix_matches_nested_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "rules" / "architecture.yml").write_text(
        "rules:\n  - id: pkg\n    paths:\n      include:\n        - backend/src/pkg\n    pattern: x = ...\n",
        encoding="utf-8",
    )
    document = build_map(repo)
    assert document["modules"]["backend/src/pkg/b.py"] == ["pkg"]
    assert document["uncovered"] == []
