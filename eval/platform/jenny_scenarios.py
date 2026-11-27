"""Map JENNY-* case ids to LiveKit-style scenario YAML under eval/scenarios/jenny_separate/."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JENNY_SEP = ROOT / "eval/scenarios/jenny_separate"

JENNY_YAML: dict[str, Path] = {
    f"JENNY-{i}": JENNY_SEP / f"{i:02d}_{name}.yaml"
    for i, name in enumerate(
        [
            "kb",
            "directory",
            "case_sms",
            "case_lookup",
            "callback_sms",
            "callback_cancel",
            "two_jobs",
            "complaint_line",
            "no_ride_booking",
            "caller_says_no",
        ],
        start=1,
    )
}


def load_scenario_block(case_id: str) -> tuple[str, str]:
    """Return (caller instructions, agent_expectations) from YAML."""
    path = JENNY_YAML.get(case_id)
    if not path or not path.is_file():
        return "", ""
    text = path.read_text(encoding="utf-8")

    def block(key: str) -> str:
        m = re.search(rf"^\s*{re.escape(key)}:\s*\|\s*\n((?:[ ].*\n?)*)", text, re.MULTILINE)
        if m:
            lines = m.group(1).splitlines()
            return "\n".join(ln[1:] if ln.startswith(" ") else ln for ln in lines).strip()
        m = re.search(rf'^\s*{re.escape(key)}:\s*>?\s*\n?\s*(.+)', text, re.MULTILINE | re.DOTALL)
        if m:
            raw = m.group(1).split("\n    ", 1)[0].strip()
            return raw
        return ""

    return block("instructions"), block("agent_expectations")