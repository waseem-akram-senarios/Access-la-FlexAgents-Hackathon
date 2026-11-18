"""Compare two eval JSON reports for regressions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def diff_reports(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    base_by_id = {r["id"]: r for r in baseline.get("results", [])}
    cur_by_id = {r["id"]: r for r in current.get("results", [])}
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    new_failures: list[str] = []
    for case_id, cur in cur_by_id.items():
        base = base_by_id.get(case_id)
        if base is None:
            if not cur.get("passed"):
                new_failures.append(case_id)
            continue
        if base.get("passed") and not cur.get("passed"):
            regressions.append(
                {
                    "id": case_id,
                    "from_score": base.get("score"),
                    "to_score": cur.get("score"),
                    "hard_fail": cur.get("hard_fail"),
                }
            )
        elif (not base.get("passed")) and cur.get("passed"):
            improvements.append({"id": case_id, "to_score": cur.get("score")})
        elif float(cur.get("score", 0)) + 5 < float(base.get("score", 0)):
            regressions.append(
                {
                    "id": case_id,
                    "from_score": base.get("score"),
                    "to_score": cur.get("score"),
                    "kind": "score_drop",
                }
            )
    return {
        "baseline_score": baseline.get("overall_score"),
        "current_score": current.get("overall_score"),
        "score_delta": round(
            float(current.get("overall_score", 0)) - float(baseline.get("overall_score", 0)),
            2,
        ),
        "regressions": regressions,
        "improvements": improvements,
        "new_failures": new_failures,
        "critical_delta": int(current.get("critical_failures", 0))
        - int(baseline.get("critical_failures", 0)),
    }
