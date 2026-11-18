"""L1–L7 evaluation framework tests (sandbox only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.agents.registry import discover_agents, implemented_agents
from eval.engine.models import AssertionResult, ScenarioResult, TestCase, TestLevel
from eval.engine.report import report_to_dict, write_json, write_markdown
from eval.engine.runner import EvalRunner, load_scenarios
from eval.engine.sandbox import assert_not_production_url, sandbox_client
from eval.engine.scoring import HARD_FAIL_CODES, WEIGHTS, score_assertions, score_scenario


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100.0


def test_discover_implemented_agents():
    all_agents = discover_agents()
    implemented = implemented_agents()
    assert {a.id for a in implemented} == {
        "general_inquiry",
        "answer_policy",
        "find_department",
        "log_case",
        "book_callback",
    }
    assert any(not a.implemented and a.id == "sales" for a in all_agents)


def test_sandbox_blocks_prod_flag():
    with pytest.raises(RuntimeError, match="blocked"):
        with sandbox_client(allow_prod=True):
            pass


def test_sandbox_blocks_external_hosts():
    with pytest.raises(RuntimeError):
        assert_not_production_url("https://api.twilio.com/sms")
    with pytest.raises(RuntimeError):
        assert_not_production_url("https://access-la-flexagents-api.vercel.app/cases")


def test_hard_fail_zeroes_score():
    case = TestCase(
        id="t",
        title="t",
        level=TestLevel.L2_INTEGRATION_TOOL,
        agent="log_case",
        category="log_case",
        input={},
        hard_fail_on=["prompt_injection_bypass"],
    )
    result = ScenarioResult(
        case=case,
        passed=True,
        assertions=[
            AssertionResult("task_ok", True, category="task"),
            AssertionResult("prompt_injection_bypass", False, category="security"),
        ],
    )
    scored = score_scenario(result)
    assert scored.hard_fail is True
    assert scored.passed is False
    assert scored.score == 0.0


def test_score_empty_buckets_full_credit():
    score, breakdown = score_assertions(
        [AssertionResult("task_create_case", True, category="task")]
    )
    assert breakdown["task_success"] == 30.0
    assert breakdown["security_safety"] == 20.0
    assert score == 100.0


def test_load_scenarios_covers_levels():
    cases = load_scenarios()
    assert len(cases) >= 10
    levels = {int(c.level) for c in cases}
    assert {1, 2, 3, 4, 5, 6, 7}.issubset(levels)


def test_proof_gi_lost_item_suite():
    report = EvalRunner().run(tags=["proof"])
    assert report.passed >= 1
    assert report.critical_failures == 0
    assert report.overall_score >= 90
    gi = next(c for c in report.scorecards if c.agent == "general_inquiry")
    assert gi.readiness in {"ready", "conditional"}


def test_full_eval_suite_no_critical(tmp_path: Path):
    report = EvalRunner().run()
    assert report.critical_failures == 0
    assert report.failed == 0
    assert report.overall_score >= 90
    assert report.readiness in {"ready", "conditional"}
    write_json(report, tmp_path / "latest.json")
    write_markdown(report, tmp_path / "latest.md")
    payload = report_to_dict(report)
    assert payload["passed"] == report.passed
    assert any(c["agent"] == "sales" and c["readiness"] == "not_implemented" for c in payload["scorecards"])


def test_security_gate_tag():
    report = EvalRunner().run(tags=["gate"])
    assert report.failed == 0
    assert report.critical_failures == 0


def test_existing_api_tests_still_importable():
    """Fast path CI still uses classic pytest against the same sandbox client pattern."""
    from tests.test_vertical import test_vertical_lost_item_full_slice

    assert callable(test_vertical_lost_item_full_slice)
