"""Go/no-go gates from the team's L1–L7 release criteria."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from eval.engine.models import EvalReport, ScenarioResult

# User criteria:
# L1 Unit          — 100% critical rules pass
# L2 Integration   — 100% critical tool contracts pass
# L3 Agent         — ≥95% task success on evaluation set
# L4 Multi-agent   — ≥95% successful handoffs
# L5 E2E           — 100% critical customer journeys pass
# L6 Production    — Monitoring, alerts and rollback ready
# L7 Business      — Validated against real customer KPIs


@dataclass
class LevelGate:
    level: int
    name: str
    criterion: str
    status: str  # pass | fail | not_tested | partial
    measured: str
    detail: str = ""


@dataclass
class AgentJudgment:
    agent: str
    gates: list[LevelGate] = field(default_factory=list)
    passed_gates: int = 0
    failed_gates: int = 0
    not_tested: int = 0
    overall: str = "not_ready"  # ready | conditional | blocked | not_ready
    rank_score: float = 0.0
    notes: list[str] = field(default_factory=list)


def _rows(results: list[ScenarioResult], agent: str, level: int) -> list[ScenarioResult]:
    return [r for r in results if r.case.agent == agent and int(r.case.level) == level]


def _critical(rows: list[ScenarioResult]) -> list[ScenarioResult]:
    return [r for r in rows if "critical" in r.case.tags or r.case.hard_fail_on]


def _pass_rate(rows: list[ScenarioResult]) -> float | None:
    if not rows:
        return None
    return 100.0 * sum(1 for r in rows if r.passed) / len(rows)


def _gate_l1(rows: list[ScenarioResult]) -> LevelGate:
    crit = _critical(rows) or rows
    if not rows:
        return LevelGate(1, "Unit", "100% critical rules pass", "not_tested", "0 cases")
    rate = _pass_rate(crit)
    ok = rate == 100.0 and not any(r.hard_fail for r in crit)
    return LevelGate(
        1,
        "Unit",
        "100% critical rules pass",
        "pass" if ok else "fail",
        f"{rate:.0f}% of {len(crit)} critical rule case(s)",
    )


def _gate_l2(rows: list[ScenarioResult]) -> LevelGate:
    crit = [r for r in rows if "critical" in r.case.tags or "integration" in r.case.tags] or rows
    if not rows:
        return LevelGate(
            2, "Integration", "100% critical tool contracts pass", "not_tested", "0 cases"
        )
    rate = _pass_rate(crit)
    ok = rate == 100.0
    return LevelGate(
        2,
        "Integration",
        "100% critical tool contracts pass",
        "pass" if ok else "fail",
        f"{rate:.0f}% of {len(crit)} tool-contract case(s)",
    )


def _gate_l3(rows: list[ScenarioResult]) -> LevelGate:
    if not rows:
        return LevelGate(
            3, "Agent", "≥95% task success on evaluation set", "not_tested", "0 cases"
        )
    rate = _pass_rate(rows)
    ok = rate is not None and rate >= 95.0
    return LevelGate(
        3,
        "Agent",
        "≥95% task success on evaluation set",
        "pass" if ok else "fail",
        f"{rate:.1f}% task success ({sum(1 for r in rows if r.passed)}/{len(rows)})",
    )


def _gate_l4(rows: list[ScenarioResult]) -> LevelGate:
    handoffs = [
        r
        for r in rows
        if "multi-agent" in r.case.tags or "orchestration" in r.case.tags or "handoff" in r.case.tags
    ] or rows
    if not rows:
        return LevelGate(
            4, "Multi-agent", "≥95% successful handoffs", "not_tested", "0 cases"
        )
    rate = _pass_rate(handoffs)
    ok = rate is not None and rate >= 95.0
    return LevelGate(
        4,
        "Multi-agent",
        "≥95% successful handoffs",
        "pass" if ok else "fail",
        f"{rate:.1f}% handoff success ({len(handoffs)} case(s))",
    )


def _gate_l5(rows: list[ScenarioResult]) -> LevelGate:
    journeys = [r for r in rows if "critical" in r.case.tags or "e2e" in r.case.tags] or rows
    if not rows:
        return LevelGate(
            5, "E2E", "100% critical customer journeys pass", "not_tested", "0 cases"
        )
    rate = _pass_rate(journeys)
    ok = rate == 100.0
    return LevelGate(
        5,
        "E2E",
        "100% critical customer journeys pass",
        "pass" if ok else "fail",
        f"{rate:.0f}% of {len(journeys)} critical journey(s)",
    )


def _gate_l6(rows: list[ScenarioResult], *, has_ci: bool) -> LevelGate:
    """Production readiness: reliability cases + CI/monitoring artifacts present."""
    if not rows and not has_ci:
        return LevelGate(
            6,
            "Production",
            "Monitoring, alerts and rollback ready",
            "not_tested",
            "no L6 cases; CI/monitoring not verified",
        )
    rate = _pass_rate(rows) if rows else 100.0
    parts = []
    if rows:
        parts.append(f"L6 cases {rate:.0f}% ({len(rows)})")
    parts.append("CI workflow present" if has_ci else "CI missing")
    # Rollback surrogate: sandbox reset + hard-fail security gates documented
    ok = (rate is None or rate == 100.0) and has_ci
    status = "pass" if ok else ("partial" if has_ci or (rate == 100.0) else "fail")
    if not rows and has_ci:
        status = "partial"
        parts.append("no agent-specific L6 reliability cases")
    return LevelGate(
        6,
        "Production",
        "Monitoring, alerts and rollback ready",
        status,
        "; ".join(parts),
        detail="Alerts = eval critical hard-fail + CI gate; rollback = sandbox reset / revert deploy",
    )


def _gate_l7(rows: list[ScenarioResult]) -> LevelGate:
    kpis = [r for r in rows if "business" in r.case.tags or "kpi" in r.case.tags] or rows
    if not rows:
        return LevelGate(
            7,
            "Business",
            "Validated against real customer KPIs",
            "not_tested",
            "0 KPI cases (staging chat KPIs not wired)",
        )
    rate = _pass_rate(kpis)
    # Local KPI proxies (case created, callback booked) — not live customer analytics
    ok = rate == 100.0
    return LevelGate(
        7,
        "Business",
        "Validated against real customer KPIs",
        "pass" if ok else "fail",
        f"{rate:.0f}% KPI proxy cases ({len(kpis)}); sandbox KPIs only — not live FlexAgents analytics",
    )


def judge_agent(
    agent: str,
    results: list[ScenarioResult],
    *,
    has_ci: bool,
) -> AgentJudgment:
    gates = [
        _gate_l1(_rows(results, agent, 1)),
        _gate_l2(_rows(results, agent, 2)),
        _gate_l3(_rows(results, agent, 3)),
        _gate_l4(_rows(results, agent, 4)),
        _gate_l5(_rows(results, agent, 5)),
        _gate_l6(_rows(results, agent, 6), has_ci=has_ci),
        _gate_l7(_rows(results, agent, 7)),
    ]
    judgment = AgentJudgment(agent=agent, gates=gates)
    for g in gates:
        if g.status == "pass":
            judgment.passed_gates += 1
        elif g.status == "fail":
            judgment.failed_gates += 1
        else:
            judgment.not_tested += 1

    # Hard blockers: any fail on L1/L2/L5 critical 100% gates
    hard = [g for g in gates if g.level in {1, 2, 5} and g.status == "fail"]
    soft_fail = [g for g in gates if g.level in {3, 4} and g.status == "fail"]

    if hard:
        judgment.overall = "blocked"
        judgment.notes.append("Failed a 100% critical gate (L1/L2/L5).")
    elif soft_fail:
        judgment.overall = "not_ready"
        judgment.notes.append("Below 95% on L3 task success and/or L4 handoffs.")
    elif judgment.passed_gates == 7:
        judgment.overall = "ready"
    elif judgment.passed_gates >= 4 and judgment.failed_gates == 0:
        judgment.overall = "conditional"
        judgment.notes.append("No failed gates, but some levels not tested or only partial.")
    else:
        judgment.overall = "not_ready"

    # Rank: passed gates first, then fewer not_tested, then prefer pass over partial
    partial = sum(1 for g in gates if g.status == "partial")
    judgment.rank_score = judgment.passed_gates * 10 - judgment.failed_gates * 20 - judgment.not_tested - partial * 0.5
    return judgment


def judge_report(report: EvalReport, *, has_ci: bool = True) -> dict[str, Any]:
    agents = sorted({r.case.agent for r in report.results})
    judgments = [judge_agent(a, report.results, has_ci=has_ci) for a in agents]
    judgments.sort(key=lambda j: (-j.rank_score, j.agent))

    criteria = [
        {"level": 1, "name": "Unit", "rule": "100% critical rules pass"},
        {"level": 2, "name": "Integration", "rule": "100% critical tool contracts pass"},
        {"level": 3, "name": "Agent", "rule": "≥95% task success on evaluation set"},
        {"level": 4, "name": "Multi-agent", "rule": "≥95% successful handoffs"},
        {"level": 5, "name": "E2E", "rule": "100% critical customer journeys pass"},
        {"level": 6, "name": "Production", "rule": "Monitoring, alerts and rollback ready"},
        {"level": 7, "name": "Business", "rule": "Validated against real customer KPIs"},
    ]

    winner = judgments[0] if judgments else None
    return {
        "criteria": criteria,
        "judgments": [
            {
                "agent": j.agent,
                "overall": j.overall,
                "passed_gates": j.passed_gates,
                "failed_gates": j.failed_gates,
                "not_tested": j.not_tested,
                "rank_score": j.rank_score,
                "notes": j.notes,
                "gates": [asdict(g) for g in j.gates],
            }
            for j in judgments
        ],
        "best_agent": winner.agent if winner else None,
        "best_overall": winner.overall if winner else None,
    }


def format_judgment_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent judgment (team L1–L7 criteria)",
        "",
        "| Level | Name | Criterion |",
        "|------:|------|-----------|",
    ]
    for c in payload["criteria"]:
        lines.append(f"| L{c['level']} | {c['name']} | {c['rule']} |")
    lines.extend(["", f"**Best agent by gates:** `{payload.get('best_agent')}` ({payload.get('best_overall')})", ""])
    for j in payload["judgments"]:
        lines.extend(
            [
                f"## {j['agent']} — **{j['overall']}** ({j['passed_gates']}/7 gates pass)",
                "",
                "| Level | Status | Measured |",
                "|------|--------|----------|",
            ]
        )
        for g in j["gates"]:
            lines.append(
                f"| L{g['level']} {g['name']} | {g['status']} | {g['measured']} |"
            )
        for note in j.get("notes") or []:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)
