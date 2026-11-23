"""Run independent role-specific design reviews and write one report each."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_review

ROLES: dict[str, str] = {
    "problem": (
        "Review the problem framing and decision rationale. Check the evidence for the problem, "
        "constraints, non-goals, options considered, decision criteria, the stated why, assumptions "
        "and falsifiers. Ignore implementation details unless they contradict the stated why. "
        "If no design brief is supplied, return insufficient-context and ask for one."
    ),
    "architecture": (
        "Review module boundaries, ownership, data flow, coupling, abstraction level and consistency "
        "with existing ADRs. Ignore security, tests and style unless they change the architecture."
    ),
    "failure": (
        "Review failure modes: retries, timeouts, concurrency, partial failure, rollback, recovery "
        "and observability. Ignore style and naming."
    ),
    "security": (
        "Review trust boundaries, secrets, authentication, authorization, input validation and data "
        "exposure. Report only design-level security concerns unless an implementation detail makes "
        "the design unsafe."
    ),
    "evidence": (
        "Review the evidence plan: what tests, proofs, benchmarks, metrics or observations would "
        "falsify the design, and whether the change actually provides them. Ignore style."
    ),
}
VERDICTS = {"coherent", "needs-decision", "insufficient-context", "concern"}
CONFIDENCE = {"low", "medium", "high"}
REQUIRED = ("role", "verdict", "findings", "questions", "evidence", "confidence")


class PanelError(RuntimeError):
    """Raised when a panel report cannot be produced."""


def build_role_prompt(role: str, diff: str, docs: str, brief: str) -> str:
    """Build one independent reviewer prompt."""
    return f"""You are the {role} reviewer on an independent design panel. Review only this lens.
Do not repeat other reviewers. The report is advisory; do not approve or reject.

Return ONLY a JSON object:
{{
  "role": "{role}",
  "verdict": "coherent | needs-decision | insufficient-context | concern",
  "findings": ["decision-level finding with file/symbol evidence"],
  "questions": ["specific question for the author"],
  "evidence": ["test, proof, benchmark or observation needed"],
  "confidence": "low | medium | high"
}}

Rules:
- Cite files or symbols. Separate facts from hypotheses.
- For the problem role, the design brief is the primary evidence; without it, do not infer the why.
- Do not report formatting, naming taste, test counts or generic best practices.
- At most five items per list. Be concise.

Role: {ROLES[role]}

Design brief (author's stated why; may be missing):
{brief or "(no design brief supplied)"}

Repository design documents:
{docs}

Diff:
{diff}
"""


def parse_role_report(text: str, role: str) -> dict[str, Any]:
    """Extract and validate one role report."""
    stripped = text.strip()
    fenced = None
    if "```" in stripped:
        start = stripped.find("```")
        end = stripped.find("```", start + 3)
        fenced = stripped[stripped.find("\n", start) + 1 : end]
    candidate = fenced or stripped
    decoder = json.JSONDecoder()
    for index, char in enumerate(candidate):
        if char != "{":
            continue
        try:
            report, _ = decoder.raw_decode(candidate[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(report, dict) or not all(key in report for key in REQUIRED):
            continue
        if report.get("role") != role:
            raise PanelError(f"expected role {role!r}, got {report.get('role')!r}")
        if report.get("verdict") not in VERDICTS or report.get("confidence") not in CONFIDENCE:
            raise PanelError(f"invalid verdict or confidence for {role}")
        for key in ("findings", "questions", "evidence"):
            values = report.get(key)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise PanelError(f"{role}.{key} must be a list of strings")
        return report
    raise PanelError(f"{role} reviewer did not return a complete JSON report")


def render_role(report: dict[str, Any]) -> str:
    """Render one role report as Markdown."""
    lines = [
        f"# Design review: {report['role']}",
        "",
        f"**Verdict:** `{report['verdict']}`",
        f"**Confidence:** `{report['confidence']}`",
        "",
    ]
    for key, title in (
        ("findings", "Findings"),
        ("questions", "Questions"),
        ("evidence", "Evidence needed"),
    ):
        lines += [f"## {title}", ""]
        values = report.get(key, [])
        lines += [f"- {item}" for item in values] if values else ["- None stated."]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_index(reports: dict[str, dict[str, Any]], errors: dict[str, str]) -> str:
    """Render a deterministic index of the independent reports."""
    lines = [
        "# Design review panel",
        "",
        "| Role | Verdict | Confidence | Top finding |",
        "| --- | --- | --- | --- |",
    ]
    for role in sorted(set(reports) | set(errors)):
        if role in errors:
            lines.append(f"| {role} | error | - | {errors[role]} |")
            continue
        report = reports[role]
        top = report.get("findings", ["-"])[0] if report.get("findings") else "-"
        lines.append(f"| [{role}]({role}.md) | {report['verdict']} | {report['confidence']} | {top[:160]} |")
    lines += ["", "Each report is independent; disagreements are intentional and are not averaged.", ""]
    return "\n".join(lines)


def run_panel(options: argparse.Namespace) -> int:
    """Collect context, run one model call per role, and write reports."""
    repo = options.repo.resolve()
    try:
        diff = (
            design_review._cap(
                options.diff_file.read_text(encoding="utf-8", errors="replace"),
                options.max_diff_chars,
            )
            if options.diff_file
            else design_review.collect_diff(repo, options.base, options.head, options.max_diff_chars)
        )
        if not diff.strip():
            raise PanelError("no changes to review")
        docs = design_review.collect_docs(repo, options.head, options.max_doc_chars)
        brief = options.brief.read_text(encoding="utf-8", errors="replace") if options.brief else ""
        roles = [role.strip() for role in options.roles.split(",") if role.strip()]
        unknown = [role for role in roles if role not in ROLES]
        if unknown:
            raise PanelError(f"unknown roles: {', '.join(unknown)}")
        prompts = {
            role: build_role_prompt(
                role,
                design_review.redact(diff),
                design_review.redact(docs),
                design_review.redact(brief),
            )
            for role in roles
        }
    except (OSError, design_review.ReviewError, PanelError) as error:
        print(f"design panel failed: {error}", file=sys.stderr)
        return 2
    if options.dry_run:
        for role, prompt in prompts.items():
            print(f"===== {role} =====\n{prompt}")
        return 0
    api_key = os.environ.get("DESIGN_REVIEW_API_KEY") or os.environ.get("ZEN_API_KEY", "")
    if not api_key:
        print("DESIGN_REVIEW_API_KEY or ZEN_API_KEY is required", file=sys.stderr)
        return 2
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    def call(role: str) -> tuple[str, dict[str, Any]]:
        raw = design_review.complete(
            prompts[role],
            base_url=options.api_base,
            api_key=api_key,
            model=options.model,
            session=options.session,
            timeout=600,
            max_tokens=options.max_tokens,
        )
        return role, parse_role_report(raw, role)

    with ThreadPoolExecutor(max_workers=options.max_workers) as pool:
        futures = {pool.submit(call, role): role for role in roles}
        for future in as_completed(futures):
            role = futures[future]
            try:
                _role, report = future.result()
                reports[role] = report
            except Exception as error:
                errors[role] = str(error)
    try:
        options.out_dir.mkdir(parents=True, exist_ok=True)
        for role, report in reports.items():
            (options.out_dir / f"{role}.md").write_text(render_role(report), encoding="utf-8")
            (options.out_dir / f"{role}.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        (options.out_dir / "index.md").write_text(render_index(reports, errors), encoding="utf-8")
    except OSError as error:
        print(f"design panel failed to write reports: {error}", file=sys.stderr)
        return 2
    if errors:
        for role, message in errors.items():
            print(f"{role}: {message}", file=sys.stderr)
        return 2
    print(f"wrote {len(reports)} reports to {options.out_dir}")
    return 0


def main(argv: list[str]) -> int:
    """Parse arguments and run the panel."""
    parser = argparse.ArgumentParser(description="Independent role-specific design reviews")
    parser.add_argument("--repo", type=Path, default=Path())
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--diff-file", type=Path)
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("reports/design-review"))
    parser.add_argument("--roles", default=",".join(ROLES))
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--max-diff-chars", type=int, default=50_000)
    parser.add_argument("--max-doc-chars", type=int, default=30_000)
    parser.add_argument("--max-tokens", type=int, default=12_000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=os.environ.get("DESIGN_REVIEW_MODEL", "deepseek-v4.1-flash"))
    parser.add_argument(
        "--api-base", default=os.environ.get("DESIGN_REVIEW_API_BASE", "https://opencode.ai/zen/go/v1")
    )
    parser.add_argument(
        "--session", default=os.environ.get("DESIGN_REVIEW_SESSION", "22222222-2222-4222-8222-222222222222")
    )
    return run_panel(parser.parse_args(argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
