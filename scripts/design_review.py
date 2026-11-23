"""Advisory design review of a git diff using a language model."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DOCS = (
    "AGENTS.md",
    "docs/architecture.md",
    "docs/routing.md",
    "docs/providers.md",
    "docs/gates.md",
    "docs/adr/index.md",
)
SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b(\s*[:=]\s*)(\S+)")
REQUIRED = (
    "summary",
    "intent",
    "assumptions",
    "invariants",
    "alternatives",
    "risks",
    "missing_evidence",
    "questions",
    "verdict",
)


class ReviewError(RuntimeError):
    """Raised when the review cannot be produced."""


def redact(text: str) -> str:
    """Replace obvious secret assignments before sending context to the model."""
    return SECRET_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ReviewError(f"git {' '.join(args)} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def collect_diff(repo: Path, base: str, head: str, limit: int) -> str:
    """Return a merge-base diff with a size cap."""
    merge_base = _git(repo, "merge-base", base, head).strip()
    diff = _git(repo, "diff", "--no-color", "--no-ext-diff", "--unified=80", merge_base, head)
    if len(diff) > limit:
        diff = diff[:limit] + "\n\n[diff truncated]\n"
    return diff


def collect_docs(repo: Path, limit: int) -> str:
    """Return the design documents that are available."""
    chunks: list[str] = []
    used = 0
    for name in DOCS:
        path = repo / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        remaining = limit - used
        if remaining <= 0:
            break
        chunks.append(f"### {name}\n{text[:remaining]}")
        used += len(text[:remaining])
    return "\n\n".join(chunks)


def build_prompt(diff: str, docs: str) -> str:
    """Build a design-review prompt that asks for reasons, not style nits."""
    return f"""You are a design reviewer for a production LLM gateway. Review the change below
for design coherence and reasons, not for style or lint issues.

Return ONLY a JSON object with this shape:
{{
  "summary": "one paragraph",
  "intent": "the problem and constraints you infer, with evidence",
  "assumptions": ["assumption — evidence or confidence"],
  "invariants": ["invariant the change must preserve — evidence"],
  "alternatives": [{{"option": "name", "tradeoffs": "cost/benefit versus the chosen change"}}],
  "risks": ["concrete failure mode, coupling or operational risk"],
  "missing_evidence": ["test, proof, benchmark or observation needed"],
  "questions": ["specific question for the author"],
  "verdict": "coherent | needs-discussion | insufficient-context"
}}

Rules:
- Cite file paths or symbols. If evidence is absent, say so; do not invent requirements.
- Propose at least two alternatives, including "do nothing smaller" when plausible.
- Distinguish facts in the diff from hypotheses.
- Do not approve or reject; the report is advisory.
- Do not review formatting, naming taste or test counts.
- Be concise. Each list has at most six items.

Repository design documents:
{docs}

Change:
{diff}
"""


def extract_json(text: str) -> dict[str, Any]:
    """Extract the JSON object returned by the model."""
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    candidate = fenced.group(1) if fenced else stripped
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ReviewError("model did not return a JSON object")
    try:
        report = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as error:
        raise ReviewError(f"model returned invalid JSON: {error}") from error
    if not isinstance(report, dict):
        raise ReviewError("model report is not a JSON object")
    missing = [key for key in REQUIRED if key not in report]
    if missing:
        raise ReviewError(f"model report is missing keys: {', '.join(missing)}")
    return report


def complete(prompt: str, *, base_url: str, api_key: str, model: str, session: str, timeout: int) -> str:
    """Call an OpenAI-compatible chat completion endpoint."""
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4000,
        }
    ).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "polygate-design-review",
        "x-opencode-session": session,
    }
    request = urllib.request.Request(  # noqa: S310
        f"{base_url.rstrip('/')}/chat/completions", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ReviewError(f"model request failed: {error}") from error
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as error:
        raise ReviewError(f"unexpected model response: {payload}") from error


def render_markdown(report: dict[str, Any]) -> str:
    """Render a report as Markdown."""
    lines = ["# Design review", "", f"**Verdict:** `{report['verdict']}`", "", str(report["summary"]), ""]
    lines += ["## Intent", "", str(report["intent"]), ""]
    for key, title in (
        ("assumptions", "Assumptions"),
        ("invariants", "Invariants"),
        ("risks", "Risks"),
        ("missing_evidence", "Missing evidence"),
        ("questions", "Questions for the author"),
    ):
        lines += [f"## {title}", ""]
        values = report.get(key, [])
        lines += (
            [f"- {item}" for item in values] if isinstance(values, list) and values else ["- None stated."]
        )
        lines.append("")
    lines += ["## Alternatives", ""]
    alternatives = report.get("alternatives", [])
    if isinstance(alternatives, list):
        for item in alternatives:
            if isinstance(item, dict):
                lines.append(f"- **{item.get('option', '?')}**: {item.get('tradeoffs', '')}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    """Run the review and print Markdown or JSON."""
    parser = argparse.ArgumentParser(description="Advisory design review")
    parser.add_argument("--repo", type=Path, default=Path())
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--diff-file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-diff-chars", type=int, default=50_000)
    parser.add_argument("--max-doc-chars", type=int, default=30_000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=os.environ.get("DESIGN_REVIEW_MODEL", "deepseek-v4.1-flash"))
    parser.add_argument(
        "--api-base", default=os.environ.get("DESIGN_REVIEW_API_BASE", "https://opencode.ai/zen/go/v1")
    )
    parser.add_argument(
        "--session", default=os.environ.get("DESIGN_REVIEW_SESSION", "22222222-2222-4222-8222-222222222222")
    )
    options = parser.parse_args(argv[1:])
    repo = options.repo.resolve()
    try:
        diff = (
            options.diff_file.read_text(encoding="utf-8", errors="replace")
            if options.diff_file
            else collect_diff(repo, options.base, options.head, options.max_diff_chars)
        )
        docs = collect_docs(repo, options.max_doc_chars)
        prompt = build_prompt(redact(diff), redact(docs))
        if options.dry_run:
            print(prompt)
            return 0
        api_key = os.environ.get("DESIGN_REVIEW_API_KEY") or os.environ.get("ZEN_API_KEY", "")
        if not api_key:
            print("DESIGN_REVIEW_API_KEY or ZEN_API_KEY is required", file=sys.stderr)
            return 2
        raw = complete(
            prompt,
            base_url=options.api_base,
            api_key=api_key,
            model=options.model,
            session=options.session,
            timeout=600,
        )
        report = extract_json(raw)
        output = (
            json.dumps(report, indent=2, ensure_ascii=False)
            if options.format == "json"
            else render_markdown(report)
        )
    except (OSError, ReviewError) as error:
        print(f"design review failed: {error}", file=sys.stderr)
        return 2
    if options.out:
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
