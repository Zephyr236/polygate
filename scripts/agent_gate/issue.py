"""Extract a candidate JSON and patch from an agent-created issue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MARKER = "<!-- agent-candidate:v1 -->"
JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.DOTALL)
DIFF_BLOCK = re.compile(r"```diff\s*(.*?)```", re.DOTALL)
ALLOWED_PREFIXES = (
    "agent/candidates/",
    "agent/fixtures/",
    "rules/candidates/",
    "backend/tests/agent/",
    "docs/proposals/",
    "scripts/agent_checks/",
)
MAX_PATCH_BYTES = 200_000


class IssueError(ValueError):
    """Raised when an issue cannot be turned into a candidate."""


@dataclass(frozen=True)
class Extracted:
    """Paths of the extracted candidate and patch."""

    candidate: Path
    patch: Path


def _diff_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("+++ b/", "--- a/")):
            paths.append(line[6:].strip())
        elif line.startswith("diff --git a/"):
            parts = line.split(" ")
            if len(parts) >= 4:
                paths.extend([parts[2][2:], parts[3][2:]])
    return paths


def validate_patch_paths(patch: str) -> None:
    """Reject patches that touch anything outside the candidate prefixes."""
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise IssueError("patch is too large")
    for path in _diff_paths(patch):
        if path.startswith("/") or ".." in Path(path).parts:
            raise IssueError(f"patch contains an unsafe path: {path}")
        if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            raise IssueError(f"patch path is not allowed: {path}")


def extract_body(body: str, out_dir: Path) -> Extracted:
    """Parse the candidate JSON and diff from an issue body."""
    if MARKER not in body:
        raise IssueError("issue is missing the agent-candidate marker")
    payload = body.split(MARKER, 1)[1]
    json_match = JSON_BLOCK.search(payload)
    diff_match = DIFF_BLOCK.search(payload)
    if json_match is None or diff_match is None:
        raise IssueError("issue must contain json and diff fenced blocks")
    try:
        meta = json.loads(json_match.group(1))
    except json.JSONDecodeError as error:
        raise IssueError(f"candidate JSON is invalid: {error}") from error
    if not isinstance(meta, dict):
        raise IssueError("candidate must be a JSON object")
    patch = diff_match.group(1)
    validate_patch_paths(patch)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate = out_dir / "candidate.json"
    patch_file = out_dir / "candidate.patch"
    candidate.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    patch_file.write_text(patch, encoding="utf-8")
    return Extracted(candidate, patch_file)


def extract_event(event: dict[str, Any], out_dir: Path) -> Extracted:
    """Validate the issue author and label, then extract the payload."""
    issue = event.get("issue")
    label = event.get("label")
    if not isinstance(issue, dict) or not isinstance(label, dict):
        raise IssueError("event must be an issue labeled event")
    author = str((issue.get("user") or {}).get("login", ""))
    if author != "github-actions[bot]":
        raise IssueError(f"unexpected issue author: {author}")
    if label.get("name") != "agent-candidate":
        raise IssueError("issue is not labeled agent-candidate")
    body = str(issue.get("body") or "")
    return extract_body(body, out_dir)


def main(argv: list[str]) -> int:
    """Extract a candidate from an event payload."""
    parser = argparse.ArgumentParser(description="Extract an agent candidate from an issue event")
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    options = parser.parse_args(argv[1:])
    try:
        event = json.loads(options.event.read_text(encoding="utf-8"))
        extracted = extract_event(event, options.out_dir)
    except (OSError, json.JSONDecodeError, IssueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"candidate={extracted.candidate}")
    print(f"patch={extracted.patch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
