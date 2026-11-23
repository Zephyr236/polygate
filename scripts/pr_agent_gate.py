"""Fail when PR-Agent's latest review contains active findings."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Any

MARKER = "<!-- pr-agent-review-state:v1"
STATE_RE = re.compile(r"<!-- pr-agent-review-state:v1\n(.*?)\n-->", re.S)


class GateError(RuntimeError):
    """Raised when PR-Agent's review state cannot be evaluated."""


def parse_state(body: str) -> dict[str, Any] | None:
    """Return the review state embedded in a PR-Agent comment, if present."""
    match = STATE_RE.search(body)
    if match is None:
        return None
    try:
        state = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise GateError(f"invalid PR-Agent review state: {error}") from error
    if not isinstance(state, dict):
        raise GateError("PR-Agent review state must be an object")
    return state


def active_findings(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return findings that PR-Agent has not marked resolved."""
    findings = state.get("findings", [])
    if not isinstance(findings, list):
        raise GateError("PR-Agent findings must be a list")
    return [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("state") == "ACTIVE"
    ]


def evaluate(comments: list[dict[str, Any]], head_sha: str) -> list[dict[str, Any]]:
    """Return active findings from the latest review of ``head_sha``."""
    matching: list[dict[str, Any]] = []
    for comment in comments:
        state = parse_state(str(comment.get("body", "")))
        if state is None:
            continue
        last_run = state.get("last_run", {})
        if isinstance(last_run, dict) and last_run.get("head_sha") == head_sha:
            matching.append(state)
    if not matching:
        raise GateError(f"no PR-Agent review state for head {head_sha}")
    state = matching[-1]
    last_run = state.get("last_run", {})
    if not isinstance(last_run, dict) or not last_run.get("complete"):
        raise GateError(f"PR-Agent review for {head_sha} is incomplete")
    return active_findings(state)


def _api(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "polygate-pr-agent-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def main() -> int:
    """Evaluate the current PR and fail on active findings."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    number = os.environ.get("PR_NUMBER", "")
    if not token or not repo or not number:
        print("GITHUB_TOKEN, GITHUB_REPOSITORY and PR_NUMBER are required", file=sys.stderr)
        return 2
    try:
        pull = _api(f"/repos/{repo}/pulls/{number}", token)
        head_sha = str(pull["head"]["sha"])
        comments = _api(f"/repos/{repo}/issues/{number}/comments?per_page=100", token)
        if not isinstance(comments, list):
            raise GateError("PR comments response is not a list")
        findings = evaluate(comments, head_sha)
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"PR-Agent gate: {error}", file=sys.stderr)
        return 2
    if not findings:
        print("PR-Agent gate: no active findings")
        return 0
    print(f"PR-Agent gate: {len(findings)} active finding(s)")
    for finding in findings:
        path = finding.get("path", "?")
        line = finding.get("line_start", "?")
        body = " ".join(str(finding.get("body", "")).split())[:240]
        print(f"- {path}:{line} {body}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
