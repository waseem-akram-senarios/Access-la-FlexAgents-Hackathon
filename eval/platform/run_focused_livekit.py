#!/usr/bin/env python3
"""Run focused platform checks: lk simulate where possible, else report blockers.

Writes eval/reports/platform_focused_latest.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = [
    ("F0", "P-07", "eval/scenarios/ana_separate/02_access_program_17.yaml", "eval/staging/ana_worker.py"),
    ("F8", "—", "eval/scenarios/neo_separate/05_saturday.yaml", "eval/staging/neo_worker.py"),
    ("F3", "P-04,P-05", "eval/scenarios/neo_separate/04_route_serves_stop.yaml", "eval/staging/neo_worker.py"),
    ("F4", "P-05", "eval/scenarios/neo_separate/02_where_scheduled.yaml", "eval/staging/neo_worker.py"),
    ("F5", "P-05", "eval/scenarios/neo_separate/08_realtime_late.yaml", "eval/staging/neo_worker.py"),
    ("F6", "P-06", "eval/scenarios/neo_separate/03_routes_at_stop.yaml", "eval/staging/neo_worker.py"),
    ("F7", "orchestration", "eval/scenarios/jenny_separate/04_case_lookup.yaml", "eval/staging/flexagent_staging_worker.py"),
    ("F1", "orchestration", "eval/scenarios/ana_separate/01_no_profile.yaml", "eval/staging/ana_worker.py"),
]


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)


def try_simulate(fid: str, pid: str, scenario: str, worker: str) -> dict:
    scenario_path = ROOT / scenario
    worker_path = ROOT / worker
    out: dict = {
        "focus_id": fid,
        "platform_ids": pid,
        "scenario_yaml": scenario,
        "worker": worker,
        "status": "not_run",
        "detail": "",
    }
    if not scenario_path.is_file():
        out["status"] = "error"
        out["detail"] = "scenario file missing"
        return out
    if not worker_path.is_file():
        out["status"] = "error"
        out["detail"] = "worker file missing"
        return out
    venv = ROOT / ".venv-platform" / "bin" / "python"
    if not venv.is_file():
        out["status"] = "blocked"
        out["detail"] = "Run: uv venv .venv-platform && uv pip install livekit-agents"
        return out
    cmd = [
        "lk",
        "agent",
        "simulate",
        "--scenarios",
        str(scenario_path),
        "--yes",
        str(worker_path),
    ]
    env = {**os.environ}
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            out["status"] = "pass_runner"
            out["detail"] = combined[-2000:] if len(combined) > 2000 else combined
        else:
            out["status"] = "fail_runner"
            out["detail"] = combined[-3000:] if len(combined) > 3000 else combined
    except subprocess.TimeoutExpired:
        out["status"] = "timeout"
        out["detail"] = "simulate exceeded 600s"
    except FileNotFoundError:
        out["status"] = "blocked"
        out["detail"] = "lk CLI not installed"
    return out


def main() -> int:
    load_env()
    results = []
    for row in SCENARIOS:
        results.append(try_simulate(*row))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local_lk_agent_simulate",
        "warning": (
            "Local neo_worker mocks Knight stops — F3–F6 PASS here does NOT sign off "
            "platform P-04/P-05. Re-run F3–F6 on FlexAgents dashboard staging for gate."
        ),
        "livekit_env_configured": bool(os.environ.get("LIVEKIT_URL")),
        "results": results,
    }
    out_dir = ROOT / "eval" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "platform_focused_latest.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {out_path}")

    failed = sum(1 for r in results if r["status"] in ("fail_runner", "error", "timeout"))
    blocked = sum(1 for r in results if r["status"] == "blocked")
    return 1 if failed or blocked == len(results) else 0


if __name__ == "__main__":
    sys.exit(main())