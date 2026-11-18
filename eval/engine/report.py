"""Serialize evaluation reports to JSON and Markdown."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.engine.models import EvalReport, ScenarioResult


def _result_dict(result: ScenarioResult) -> dict[str, Any]:
    return {
        "id": result.case.id,
        "title": result.case.title,
        "agent": result.case.agent,
        "level": int(result.case.level),
        "category": result.case.category,
        "passed": result.passed,
        "score": result.score,
        "breakdown": result.breakdown,
        "latency_ms": result.latency_ms,
        "cost_units": result.cost_units,
        "hard_fail": result.hard_fail,
        "hard_fail_reasons": result.hard_fail_reasons,
        "needs_human_review": result.needs_human_review,
        "error": result.error,
        "run_index": result.run_index,
        "assertions": [asdict(a) for a in result.assertions],
        "traces": [asdict(t) for t in result.traces],
    }


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "generated_at": report.generated_at,
        "overall_score": report.overall_score,
        "passed": report.passed,
        "failed": report.failed,
        "critical_failures": report.critical_failures,
        "readiness": report.readiness,
        "scorecards": [asdict(c) for c in report.scorecards],
        "results": [_result_dict(r) for r in report.results],
    }


def write_json(report: EvalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")
    return path


def write_markdown(report: EvalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Evaluation Report",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Overall score: **{report.overall_score}/100**",
        f"- Passed: {report.passed} | Failed: {report.failed} | Critical: {report.critical_failures}",
        f"- Readiness: **{report.readiness}**",
        "",
        "## Agent scorecards",
        "",
        "| Agent | Score | Passed | Failed | Critical | Levels | Readiness |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for card in report.scorecards:
        levels = ",".join(str(l) for l in card.levels_covered) or "—"
        lines.append(
            f"| {card.agent} | {card.score} | {card.passed} | {card.failed} | "
            f"{card.critical_failures} | {levels} | {card.readiness} |"
        )
    lines.extend(["", "## Failed / critical cases", ""])
    failures = [r for r in report.results if not r.passed or r.hard_fail]
    if not failures:
        lines.append("None.")
    else:
        for result in failures:
            lines.append(
                f"- `{result.case.id}` (L{int(result.case.level)} / {result.case.agent}) "
                f"score={result.score} hard_fail={result.hard_fail}"
            )
            if result.error:
                lines.append(f"  - error: {result.error}")
            for reason in result.hard_fail_reasons:
                lines.append(f"  - hard fail: {reason}")
            for assertion in result.assertions:
                if not assertion.passed:
                    lines.append(f"  - fail: {assertion.name} — {assertion.detail}")
    lines.extend(["", "## Recommended fixes", ""])
    fixes = []
    for card in report.scorecards:
        for fix in card.recommended_fixes:
            fixes.append(f"- [{card.agent}] {fix}")
    lines.extend(fixes or ["None."])
    lines.extend(
        [
            "",
            "## Latency & cost (per case)",
            "",
            "| Case | Latency ms | Cost units |",
            "|---|---:|---:|",
        ]
    )
    for result in report.results:
        lines.append(
            f"| {result.case.id} | {result.latency_ms} | {result.cost_units} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_html(report: EvalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for card in report.scorecards:
        levels = ",".join(str(l) for l in card.levels_covered) or "—"
        rows.append(
            "<tr>"
            f"<td>{card.agent}</td><td>{card.score}</td><td>{card.passed}</td>"
            f"<td>{card.failed}</td><td>{card.critical_failures}</td>"
            f"<td>{levels}</td><td>{card.readiness}</td>"
            "</tr>"
        )
    case_rows = []
    for result in report.results:
        status = "FAIL" if not result.passed else "PASS"
        case_rows.append(
            "<tr>"
            f"<td>{result.case.id}</td><td>L{int(result.case.level)}</td>"
            f"<td>{result.case.agent}</td><td>{status}</td>"
            f"<td>{result.score}</td><td>{result.latency_ms}</td>"
            f"<td>{result.hard_fail}</td>"
            "</tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Agent Evaluation Report</title>
<style>
body{{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem;background:#f7f4ef;color:#1a1a1a}}
h1{{font-size:1.6rem}} table{{border-collapse:collapse;width:100%;margin:1rem 0;background:#fff}}
th,td{{border:1px solid #ddd;padding:.45rem .6rem;text-align:left;font-size:.9rem}}
th{{background:#ece7df}} .meta{{margin:.25rem 0}} .ready{{color:#0b6b3a;font-weight:600}}
</style></head><body>
<h1>Agent Evaluation Report</h1>
<p class="meta">Generated: {report.generated_at}</p>
<p class="meta">Overall: <strong>{report.overall_score}/100</strong> ·
Passed {report.passed} · Failed {report.failed} · Critical {report.critical_failures} ·
<span class="ready">{report.readiness}</span></p>
<h2>Scorecards</h2>
<table><thead><tr><th>Agent</th><th>Score</th><th>Passed</th><th>Failed</th>
<th>Critical</th><th>Levels</th><th>Readiness</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>Cases</h2>
<table><thead><tr><th>Case</th><th>Level</th><th>Agent</th><th>Status</th>
<th>Score</th><th>Latency ms</th><th>Hard fail</th></tr></thead>
<tbody>{''.join(case_rows)}</tbody></table>
</body></html>
"""
    path.write_text(html, encoding="utf-8")
    return path


def print_summary(report: EvalReport) -> None:
    print(
        f"Eval {report.version} | score={report.overall_score} "
        f"passed={report.passed} failed={report.failed} "
        f"critical={report.critical_failures} readiness={report.readiness}"
    )
    for card in report.scorecards:
        if card.readiness == "not_implemented":
            continue
        print(
            f"  - {card.agent}: {card.score}/100 "
            f"({card.passed} pass / {card.failed} fail) [{card.readiness}]"
        )
