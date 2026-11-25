"""Gherkin steps for the design-gate contract."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

ROOT = Path(__file__).resolve().parents[3]
FEATURE = ROOT / "specs" / "features" / "gate.feature"
scenarios(str(FEATURE))
sys.path.insert(0, str(ROOT / "scripts"))
import capability_gate
import gate_contract


@pytest.fixture()
def state() -> dict[str, Any]:
    return {}


@given(parsers.parse('the tested head is "{head}"'))
def set_tested_head(state: dict[str, Any], head: str) -> None:
    state["tested"] = head


@given(parsers.parse('the current PR head is "{head}"'))
def current_head(state: dict[str, Any], head: str) -> None:
    state["current"] = head


@when("I resolve the review target")
def resolve(state: dict[str, Any]) -> None:
    state["target"] = gate_contract.resolve_review_target(state["tested"], state["current"])


@then("the review target is empty")
def target_empty(state: dict[str, Any]) -> None:
    assert state["target"] is None


@then(parsers.parse('the review target is "{head}"'))
def target_head(state: dict[str, Any], head: str) -> None:
    assert state["target"] == head


@given("a newer final status was created after my run started")
def newer_status(state: dict[str, Any]) -> None:
    state["statuses"] = [
        {"context": "design-review", "state": "success", "created_at": "2026-11-25T10:01:00Z"}
    ]
    state["started"] = "2026-11-25T10:00:00Z"


@when("I check whether publication is superseded")
def superseded(state: dict[str, Any]) -> None:
    state["superseded"] = gate_contract.is_superseded(state["started"], state["statuses"])


@then("publication is skipped")
def skipped(state: dict[str, Any]) -> None:
    assert state["superseded"] is True


@given("the checked-in design-gate workflow")
def workflow(state: dict[str, Any]) -> None:
    state["workflow"] = ROOT / ".github" / "workflows" / "design-gate.yml"
    state["capabilities"] = ROOT / "specs" / "capabilities.yaml"


@when("I inspect its capabilities")
def inspect_capabilities(state: dict[str, Any]) -> None:
    state["violations"] = capability_gate.check(state["workflow"], state["capabilities"])


@then("the agent job has no write permissions")
def agent_read_only(state: dict[str, Any]) -> None:
    assert state["violations"] == []


@then("the publish job has the write permissions")
def publish_writes(state: dict[str, Any]) -> None:
    assert state["violations"] == []


@given("a forged pass report")
def forged_report(state: dict[str, Any]) -> None:
    state["report"] = {"verdict": "pass", "findings": []}


@given(parsers.parse('the agent job result is "{result}"'))
def gate_result(state: dict[str, Any], result: str) -> None:
    state["gate_result"] = result
    requirements = yaml.safe_load((ROOT / "specs" / "requirements.yaml").read_text())["requirements"]
    state["requirements"] = requirements


@given("no report artifact")
def no_report(state: dict[str, Any]) -> None:
    state["report"] = {}
    state["gate_result"] = "failure"
    requirements = yaml.safe_load((ROOT / "specs" / "requirements.yaml").read_text())["requirements"]
    state["requirements"] = requirements


@when("I apply the finding policy")
def apply_policy(state: dict[str, Any]) -> None:
    state["decision"] = gate_contract.decision_for_report(
        state["report"], state["requirements"], gate_result=state.get("gate_result", "success")
    )


@then(parsers.parse('the gate decision is "{decision}"'))
def gate_decision(state: dict[str, Any], decision: str) -> None:
    assert state["decision"]["status"] == decision
