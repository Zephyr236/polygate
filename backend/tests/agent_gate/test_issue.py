"""Tests for extracting candidates from agent issues."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_gate.issue import IssueError, event_from_issue, extract_body, extract_event, validate_patch_paths

BODY = """<!-- agent-candidate:v1 -->
## Candidate
```json
{"id": "candidate-1", "gap_type": "static_pattern", "artifact": "semgrep_rule"}
```
```diff
diff --git a/rules/candidates/x.yml b/rules/candidates/x.yml
new file mode 100644
--- /dev/null
+++ b/rules/candidates/x.yml
@@ -0,0 +1 @@
+rules: []
```
"""


def _event(
    body: str = BODY, author: str = "github-actions[bot]", label: str = "agent-candidate"
) -> dict[str, object]:
    return {
        "issue": {"user": {"login": author}, "body": body},
        "label": {"name": label},
    }


def test_extract_body_writes_candidate_and_patch(tmp_path: Path) -> None:
    extracted = extract_body(BODY, tmp_path)
    assert extracted.candidate.is_file()
    assert extracted.patch.is_file()
    assert '"candidate-1"' in extracted.candidate.read_text(encoding="utf-8")
    assert "rules/candidates/x.yml" in extracted.patch.read_text(encoding="utf-8")


def test_extract_event_requires_bot_author_and_label(tmp_path: Path) -> None:
    assert extract_event(_event(), tmp_path).candidate.is_file()
    assert extract_event(_event(author="app/github-actions"), tmp_path).candidate.is_file()
    with pytest.raises(IssueError, match="unexpected issue author"):
        extract_event(_event(author="attacker"), tmp_path)
    with pytest.raises(IssueError, match="not labeled"):
        extract_event(_event(label="other"), tmp_path)


def test_missing_marker_and_blocks(tmp_path: Path) -> None:
    with pytest.raises(IssueError, match="marker"):
        extract_body("no marker", tmp_path)
    with pytest.raises(IssueError, match="fenced blocks"):
        extract_body("<!-- agent-candidate:v1 -->\n```json\n{}\n```\n", tmp_path)
    with pytest.raises(IssueError, match="invalid"):
        extract_body("<!-- agent-candidate:v1 -->\n```json\n{bad}\n```\n```diff\n```\n", tmp_path)


def test_patch_paths_are_confined(tmp_path: Path) -> None:
    with pytest.raises(IssueError, match="not allowed"):
        validate_patch_paths("+++ b/.github/workflows/evil.yml\n")
    with pytest.raises(IssueError, match="unsafe"):
        validate_patch_paths("+++ b/rules/candidates/../../x.yml\n")
    validate_patch_paths("+++ b/backend/tests/agent/test_x.py\n")
    with pytest.raises(IssueError, match="too large"):
        validate_patch_paths("+++ b/backend/tests/agent/test_x.py\n" + "x" * 210_000)
    del tmp_path


def test_event_from_issue_maps_author_and_body() -> None:
    event = event_from_issue({"author": {"login": "github-actions[bot]"}, "body": "body"})
    assert event["issue"]["user"]["login"] == "github-actions[bot]"
    assert event["issue"]["body"] == "body"
    assert event["label"]["name"] == "agent-candidate"
