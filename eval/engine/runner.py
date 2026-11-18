"""Load scenarios and execute them in the sandbox."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.agents.registry import discover_agents
from eval.engine.models import (
    AgentScorecard,
    AssertionResult,
    EvalReport,
    ScenarioResult,
    TestCase,
    TestLevel,
)
from eval.engine.sandbox import sandbox_client
from eval.engine.scoring import score_scenario
from eval.engine.workflows import WORKFLOWS

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"


def _parse_level(value: Any) -> TestLevel:
    if isinstance(value, int):
        return TestLevel(value)
    text = str(value).strip().upper()
    mapping = {
        "L1": TestLevel.L1_UNIT_CONTRACT,
        "L2": TestLevel.L2_INTEGRATION_TOOL,
        "L3": TestLevel.L3_REASONING_RAG_TOOL_CHOICE,
        "L4": TestLevel.L4_MULTI_AGENT,
        "L5": TestLevel.L5_END_TO_END,
        "L6": TestLevel.L6_RELIABILITY_PERF,
        "L7": TestLevel.L7_BUSINESS_OUTCOME,
    }
    if text in mapping:
        return mapping[text]
    return TestLevel(int(text.replace("L", "")))


def load_scenarios(path: Path | None = None) -> list[TestCase]:
    root = path or SCENARIO_DIR
    cases: list[TestCase] = []
    for file in sorted(root.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        for raw in payload.get("cases", []):
            cases.append(
                TestCase(
                    id=raw["id"],
                    title=raw.get("title", raw["id"]),
                    level=_parse_level(raw["level"]),
                    agent=raw["agent"],
                    category=raw.get("category", "general"),
                    input=raw.get("input", {}),
                    expected=raw.get("expected", {}),
                    required_tools=list(raw.get("required_tools", [])),
                    forbidden_tools=list(raw.get("forbidden_tools", [])),
                    tags=list(raw.get("tags", [])),
                    repeats=int(raw.get("repeats", 1)),
                    human_review=bool(raw.get("human_review", False)),
                    hard_fail_on=list(raw.get("hard_fail_on", [])),
                )
            )
    return cases


def _readiness(score: float, critical: int, failed: int) -> str:
    if critical:
        return "blocked"
    if failed == 0 and score >= 90:
        return "ready"
    if score >= 75:
        return "conditional"
    return "not_ready"


def _apply_tool_constraints(
    case: TestCase, assertions: list[AssertionResult], traces: list
) -> list[AssertionResult]:
    used = {t.tool for t in traces if t.tool}
    out = [
        a
        for a in assertions
        if not a.name.startswith("required_tool_") and not a.name.startswith("forbidden_")
    ]
    for tool in case.required_tools:
        out.append(
            AssertionResult(
                f"required_tool_{tool}",
                tool in used,
                f"used={sorted(used)}",
                "tool",
            )
        )
    for tool in case.forbidden_tools:
        out.append(
            AssertionResult(
                f"forbidden_{tool}",
                tool not in used,
                "forbidden tool unused",
                "security" if tool in {"admin_reset", "payment"} else "tool",
            )
        )
    return out


class EvalRunner:
    def __init__(self, scenarios: list[TestCase] | None = None) -> None:
        self.scenarios = scenarios if scenarios is not None else load_scenarios()

    def run(
        self,
        *,
        agent_filter: str | None = None,
        level_filter: int | None = None,
        tags: list[str] | None = None,
    ) -> EvalReport:
        results: list[ScenarioResult] = []
        selected = self.scenarios
        if agent_filter:
            selected = [c for c in selected if c.agent == agent_filter]
        if level_filter:
            selected = [c for c in selected if int(c.level) == level_filter]
        if tags:
            wanted = set(tags)
            selected = [c for c in selected if wanted.intersection(c.tags)]

        for case in selected:
            workflow_name = case.input.get("workflow") or case.category
            workflow = WORKFLOWS.get(workflow_name)
            repeats = max(1, case.repeats)
            for run_index in range(1, repeats + 1):
                started = time.perf_counter()
                if workflow is None:
                    result = ScenarioResult(
                        case=case,
                        passed=False,
                        error=f"Unknown workflow: {workflow_name}",
                        run_index=run_index,
                    )
                    results.append(score_scenario(result))
                    continue
                try:
                    with sandbox_client() as client:
                        assertions, traces = workflow(client, case)
                    latency = (time.perf_counter() - started) * 1000
                    assertions = _apply_tool_constraints(case, assertions, traces)
                    if "perf" in case.tags and latency > 2000:
                        assertions.append(
                            AssertionResult(
                                "latency_budget",
                                False,
                                f"{latency:.1f}ms > 2000ms",
                                "perf",
                            )
                        )
                    passed = all(a.passed for a in assertions) if assertions else False
                    result = ScenarioResult(
                        case=case,
                        passed=passed,
                        assertions=assertions,
                        traces=traces,
                        latency_ms=round(latency, 2),
                        cost_units=float(len(traces)),
                        run_index=run_index,
                    )
                except Exception as exc:  # noqa: BLE001 — capture into report
                    result = ScenarioResult(
                        case=case,
                        passed=False,
                        error=str(exc),
                        run_index=run_index,
                        latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    )
                results.append(score_scenario(result))

        scorecards = self._scorecards(results)
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        critical = sum(1 for r in results if r.hard_fail)
        overall = (
            round(sum(r.score for r in results) / len(results), 2) if results else 0.0
        )
        return EvalReport(
            version="0.1.0",
            results=results,
            scorecards=scorecards,
            overall_score=overall,
            passed=passed,
            failed=failed,
            critical_failures=critical,
            readiness=_readiness(overall, critical, failed),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _scorecards(self, results: list[ScenarioResult]) -> list[AgentScorecard]:
        by_agent: dict[str, list[ScenarioResult]] = {}
        for result in results:
            by_agent.setdefault(result.case.agent, []).append(result)
        cards: list[AgentScorecard] = []
        for agent, rows in sorted(by_agent.items()):
            score = round(sum(r.score for r in rows) / len(rows), 2)
            failed = sum(1 for r in rows if not r.passed)
            critical = sum(1 for r in rows if r.hard_fail)
            fixes: list[str] = []
            for row in rows:
                if row.hard_fail:
                    fixes.extend(row.hard_fail_reasons)
                if row.error:
                    fixes.append(row.error)
                for assertion in row.assertions:
                    if not assertion.passed:
                        fixes.append(f"{row.case.id}:{assertion.name}")
            cards.append(
                AgentScorecard(
                    agent=agent,
                    score=score,
                    passed=sum(1 for r in rows if r.passed),
                    failed=failed,
                    critical_failures=critical,
                    levels_covered=sorted({int(r.case.level) for r in rows}),
                    readiness=_readiness(score, critical, failed),
                    recommended_fixes=sorted(set(fixes))[:12],
                )
            )
        for spec in discover_agents():
            if not spec.implemented and spec.id not in by_agent:
                cards.append(
                    AgentScorecard(
                        agent=spec.id,
                        score=0.0,
                        passed=0,
                        failed=0,
                        critical_failures=0,
                        readiness="not_implemented",
                        recommended_fixes=[
                            f"No {spec.domain} agent prompt/tools in this repository"
                        ],
                    )
                )
        return cards
