"""Score the four staging agents from their own prompt rules.

This does not call FlexAgents. It checks whether each pasted prompt
states its critical rules, names its tools, and contradicts itself.
Live task success, handoff rate, and customer KPIs stay unmeasured.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"


CHECKS = {
    "jenny": [
        ("voice_only", "only voice", "Sub-agents never speak to the caller."),
        ("no_invent", "Never state a fare", "No invented fare, phone, or case number."),
        ("kb_tool", "search_knowledge", "Policy questions go to search_knowledge."),
        ("dept_tool", "find_department", "Department lookup is a handoff."),
        ("case_tool", "log_case", "New complaint or lost item goes to log_case."),
        ("callback_tool", "book_callback", "Person/transfer/callback goes to book_callback."),
        ("clock_tool", "get_current_datetime", "Dates start from get_current_datetime."),
        ("holding_line", "Let me check that for you", "Holding line only until the result."),
        ("clean_yes", "Only a clean yes counts", "Writes need a clean yes."),
        ("no_ride_booking", "Do not book, change, or cancel a ride", "Jenny must not book rides."),
        ("two_jobs", "TWO JOBS IN ONE CALL", "Two issues are finished one at a time."),
        ("language", "en or es", "Handoffs carry the caller language code."),
    ],
    "amelia": [
        ("no_regreet", "Never greet or introduce yourself again", "Greeting is already spoken."),
        ("rider_lookup", "rider lookup", "Phone goes to rider lookup first."),
        ("no_invent", "Never invent times, fares", "No invented times, fares, or confirmations."),
        ("one_question", "Ask one short question per turn", "One question per turn."),
        ("booking_order", "fare calculation", "Fare then booking, each once."),
        ("no_double_book", "Do not read the trip summary yourself", "Booking step hears the yes."),
        ("return_rule", "plus 10 minutes", "Return earliest time is pickup + travel + 10."),
        ("will_call", "will-call", "Will-call is in scope."),
        ("eta_rules", "PUETA", "ETA uses PUETA and status overrides."),
        ("transfer_scope", "Transfer for emergencies", "Transfers are limited to named cases."),
        ("no_reask", "never re-ask", "Does not re-ask known details."),
    ],
    "neo": [
        ("spoken", "easy to read aloud", "Replies are spoken, not formatted."),
        ("no_markdown", "no markdown", "No markdown, bullets, or emojis."),
        ("no_transfer", "Do not offer call transfer", "Must not offer or attempt a transfer."),
        ("no_kb_offer", "Do not offer to search knowledge", "Must not offer a knowledge search."),
        ("no_extra", "not required", "No extra searches or unneeded actions."),
    ],
    "ana": [
        ("one_question", "Ask one short question", "One short question."),
        ("no_regreet", "Do not repeat the greeting", "Does not repeat the greeting."),
        ("lookup_once", "Never look up the same number twice", "Account lookup runs once."),
        ("no_invent_phone", "Never invent a number", "Does not invent a phone number."),
        ("program_id", "ProgramID", "ProgramID decides whether to ask for a rider ID."),
        ("keep_minus_one", "Keep -1 as -1", "ProgramID -1 stays -1."),
        ("no_fake_17", "Never send 17 unless the profile says 17", "Does not send ProgramID 17 by habit."),
        ("existing_rides", "Do not ask which trip", "Booked-trip answers do not ask which trip."),
        ("not_now", "Never use the current time as the pickup", "Pickup time is never 'now'."),
        ("fare_gate", "Ask payment only when the fare is above zero", "Payment only if the fare is above zero."),
        ("book_asks_yes", "The booking step asks for the yes", "Ana does not ask for the booking yes."),
        ("no_home", "Do not ask for a home address", "No home-address question."),
        ("step_once", "Call each step once", "A running step is not started again."),
    ],
}

CONFLICTS = {
    "ana": [
        (
            "cancel_conflict",
            "The opening line says 'Do not cancel.' The later section tells her to cancel and say which rides were cancelled.",
        )
    ]
}


def audit() -> dict:
    rows = []
    for name, checks in CHECKS.items():
        text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
        lowered = text.lower()
        passed = []
        failed = []
        for check_id, needle, meaning in checks:
            if needle.lower() in lowered:
                passed.append({"id": check_id, "rule": meaning})
            else:
                failed.append({"id": check_id, "rule": meaning, "missing": needle})
        conflicts = CONFLICTS.get(name, [])
        applicable = len(checks)
        score = round(100 * len(passed) / applicable, 1) if applicable else 0
        # A self-contradiction blocks a perfect critical-rules gate.
        gate = "pass" if not failed and not conflicts else "fail"
        rows.append(
            {
                "agent": name,
                "critical_rules": f"{len(passed)}/{applicable}",
                "score": score,
                "l1_critical_rules": gate,
                "conflicts": [c[1] for c in conflicts],
                "failed": failed,
            }
        )
    rows.sort(key=lambda r: (len(r["conflicts"]), -r["score"], -len(CHECKS[r["agent"]]), r["agent"]))
    return {"measured": "prompt rules only", "ranking": rows}


def main() -> None:
    payload = audit()
    out = ROOT.parent / "reports" / "four_agents.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Measured: {payload['measured']}")
    for i, row in enumerate(payload["ranking"], 1):
        print(
            f"{i}. {row['agent']}: {row['score']}/100 "
            f"rules {row['critical_rules']} L1={row['l1_critical_rules']} "
            f"conflicts={len(row['conflicts'])}"
        )
        for item in row["failed"]:
            print(f"   missing: {item['rule']}")
        for note in row["conflicts"]:
            print(f"   conflict: {note}")


if __name__ == "__main__":
    main()
