#!/usr/bin/env python3
"""Run Access LA JENNY cases one-by-one on FlexAgents staging (Start Call + per-case prompt)."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
_PLATFORM = Path(__file__).resolve().parent
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))
load_dotenv(ROOT / ".env")
import os  # noqa: E402

EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
JENNY_URL = (
    f"{BASE}/organization/6aa1562861347fe1a3087d63/agent/6af703a01d07b8f78656fe4f/test"
)
PROGRESS = ROOT / "eval/reports/access_la_voice_sim_sequential.md"
CASES_JSON = ROOT / "eval/scenarios/jenny_access_la.json"

# Extra caller lines when the agent asks (voice test page + typed Yes).
TURN_HINTS: dict[str, list[tuple[str, str]]] = {
    "JENNY-3": [
        (r"when did you leave", "Yesterday at 2 PM on route 7."),
        (r"shall i|is that right|didn't catch", "Yes."),
    ],
    "JENNY-5": [(r"shall i book|didn't catch", "Yes.")],
    "JENNY-6": [(r"shall i cancel|didn't catch", "Yes.")],
    "JENNY-7": [
        (r"is that right|is that correct|didn't catch|shall i", "Yes."),
        (r"try again|processing limit|wasn't saved", "Yes, try again. November 5 at 2 PM on route 7."),
        (r"what date and time|when did you leave the bag", "November 5 at 2 PM on route 7."),
        (r"when did that happen", "Same time — November 5 at 2 PM on route 7."),
    ],
}


def page_transcript(page) -> str:
    return page.inner_text("body")


def norm_apostrophe(s: str) -> str:
    return s.replace("\u2019", "'").replace("\u2018", "'")


def ensure_call_started(page) -> None:
    for attempt in range(3):
        end = page.locator("button:has-text('End Call')")
        if end.count() and end.first.is_visible():
            return
        start = page.locator("button:has-text('Start Call')")
        if start.count():
            start.first.click()
            time.sleep(8)
        if page.inner_text("body").find("Thanks for calling") >= 0:
            return
        time.sleep(3)


def send_and_wait(page, text: str, timeout: float = 50.0) -> str:
    box = page.locator("input[placeholder='Type a message...']")
    box.wait_for(state="visible", timeout=20000)
    before_len = len(page_transcript(page))
    box.fill(text)
    time.sleep(0.2)
    page.keyboard.press("Enter")
    t0 = time.time()
    min_wait = min(28.0, timeout * 0.55)
    deadline = t0 + timeout
    best_len = before_len
    while time.time() < deadline:
        time.sleep(2)
        body = page_transcript(page)
        best_len = max(best_len, len(body))
        if time.time() - t0 < min_wait:
            continue
        if best_len > before_len + 120:
            time.sleep(3)
            body2 = page_transcript(page)
            if len(body2) - len(body) < 40:
                break
            best_len = len(body2)
    body = page_transcript(page)
    return body[-3500:].strip()


def transcript_slice(page) -> str:
    body = page_transcript(page)
    i = body.find("Transcript")
    return body[i:] if i >= 0 else body[-6000:]


def llm_dialogue(page, case_id: str, pass_criteria: str, max_rounds: int = 16) -> None:
    from llm_caller import DONE, next_caller_line, should_stop_conversation

    for _ in range(max_rounds):
        time.sleep(4)
        full = transcript_slice(page)
        if should_stop_conversation(case_id, full):
            break
        try:
            line = next_caller_line(case_id, full, pass_criteria, opening_sent=True)
        except Exception as exc:
            print(f"  LLM caller stopped: {exc}", flush=True)
            break
        if not line or line.strip().upper() in ("[DONE]", "DONE"):
            break
        send_and_wait(page, line, timeout=40.0)


def auto_dialogue(page, case_id: str, max_rounds: int = 12) -> None:
    """Reply when the agent prompts (confirmations, dates). Works with typed chat on voice UI."""
    hints = TURN_HINTS.get(case_id, [(r"shall i|is that right|didn't catch", "Yes.")])
    last_tail = ""
    last_answer = ""
    repeat_same = 0
    for _ in range(max_rounds):
        time.sleep(4)
        tail = page_transcript(page)[-1400:].lower()
        if tail == last_tail:
            time.sleep(2)
            tail = page_transcript(page)[-1400:].lower()
        last_tail = tail
        if re.search(
            r"what would you like|what else can i help|anything else i can|is there anything else",
            tail,
        ):
            break
        if re.search(r"already on case|have those details already|details already", tail):
            break
        sent = False
        for pattern, answer in hints:
            if not re.search(pattern, tail):
                continue
            # Avoid re-filling complaint datetime while agent only references an open case.
            if case_id == "JENNY-7" and answer.startswith("Same time"):
                if "already on case" in tail or "when did that happen" not in tail:
                    continue
            send_and_wait(page, answer, timeout=22.0)
            if answer == last_answer:
                repeat_same += 1
                if repeat_same >= 2:
                    break
            else:
                repeat_same = 0
            last_answer = answer
            sent = True
            last_tail = ""
            break
        if repeat_same >= 2:
            break
        if not sent:
            if "shall i" in tail or "is that right" in tail or "didn't catch" in tail:
                send_and_wait(page, "Yes.", timeout=22.0)
                last_tail = ""
                continue
            break


def _spoken_id(text: str, prefix: str) -> bool:
    """Match AC-48260 and TTS forms like 'A C, 4 8 2 6 0' / 'C B - 3 1 0 5 0'."""
    u = text.upper()
    if re.search(rf"\b{prefix}-?\s*\d", u):
        return True
    spaced = rf"\b{prefix}\s*,?\s*(\d\s+){{3,}}\d"
    return bool(re.search(spaced, u))


def judge(case_id: str, reply: str, question: str) -> tuple[str, str]:
    r = norm_apostrophe(reply).lower()
    if not reply or len(reply) < 20:
        return "FAIL", "no/minimal reply"
    if case_id == "JENNY-1":
        if "déjeme" in r or "verificarlo" in r:
            return "FAIL", "unprompted Spanish (P-01)"
        if re.search(r"document|material", r) and not re.search(r"\$\d", reply):
            return "PASS", "named materials / no invented $"
        if ("couldn't verify" in r or "not" in r) and ("fare" in r or "verify" in r or "information" in r):
            return "PARTIAL", "honest no fare in KB — no document title"
        if re.search(r"\$\d+\.?\d*", reply):
            return "FAIL", "gave $ without clear doc"
        return "FAIL", "missing document citation pattern"
    if case_id == "JENNY-2":
        if "couldn" in r or "could not" in r or "match" in r and "department" in r:
            return "FAIL", "no department match"
        if ("lost" in r or "found" in r) and ("open" in r or "closed" in r):
            if re.search(r"1[- .]?\d{3}[- .]?\d{3}[- .]?\d{4}", reply):
                note = " (Spanish lead-in)" if "déjeme" in r or "verificarlo" in r else ""
                return "PASS", "L&F + phone + open/closed" + note
        return "FAIL", "missing L&F phone or open/closed"
    if case_id == "JENNY-3":
        if _spoken_id(reply, "AC") or "case number" in r or "logging that report" in r:
            if "text" in r or "we'll text" in r:
                return "PASS", "case flow + SMS mentioned"
        return "FAIL", "no AC- case after flow"
    if case_id == "JENNY-4":
        if _spoken_id(reply, "AC") or ("case" in r and "found" in r):
            return "PASS", "lists case(s)"
        return "FAIL", "no case list"
    if case_id == "JENNY-5":
        if ("booked" in r or "callback" in r) and (_spoken_id(reply, "CB") or "reference" in r):
            return "PASS", "callback booked with reference"
        if "shall i book" in r and "9:30" in r:
            return "FAIL", "offer made but confirm loop (harness)"
        return "FAIL", "no booked callback"
    if case_id == "JENNY-6":
        if "cancel" in r and (_spoken_id(reply, "CB") or "reference" in r):
            return "PASS", "callback cancelled"
        return "FAIL", "cancel not completed"
    if case_id == "JENNY-7":
        saved_n = len(re.findall(r"has been saved", r))
        ac_hits = len(re.findall(r"\bac\s*,?\s*(?:\d\s+){4,}\d|\bac-?\s*\d{4,}", norm_apostrophe(reply).upper()))
        if saved_n >= 2 or ac_hits >= 2:
            return "PASS", "two cases saved (lost + complaint)"
        if ("complaint has been saved" in r or "lost-item report has been saved" in r) and _spoken_id(
            reply, "AC"
        ):
            return "PASS", "two-job flow + case id"
        if "one at a time" in r or ("first" in r and "lost" in r):
            if "reporting service" in r or "wasn't saved" in r or "not been saved" in r:
                if _spoken_id(reply, "AC") or saved_n >= 1:
                    return "PARTIAL", "orchestration OK; at least one case; API/limit issues"
                return "PARTIAL", "orchestration OK; cases API failed"
        if _spoken_id(reply, "AC") and ("rude" in r or "complaint" in r) and ("bag" in r or "lost" in r):
            return "PARTIAL", "flow ran; confirm two distinct AC numbers manually"
        return "FAIL", "two-job flow incomplete"
    if case_id == "JENNY-8":
        if "customer relation" in r and re.search(r"1[- .]?\d{3}[- .]?\d{3}[- .]?\d{4}", reply):
            if "open" in r or "closed" in r:
                return "PASS", "complaint line + phone + hours"
        return "FAIL", "missing Customer Relations info"
    if case_id == "JENNY-9":
        if ("can't" in r or "cannot" in r or "can not" in r or "unable" in r) and (
            "book" in r or "ride" in r or "status" in r or "driver" in r
        ):
            if re.search(r"confirmation number|driver will arrive at \d", r):
                return "FAIL", "invented booking/ETA"
            return "PASS", "refused ride"
        return "FAIL", "did not clearly refuse"
    if case_id == "JENNY-10":
        if "won't file" in r or "won’t file" in r or "not file" in r or "understood" in r:
            return "PASS", "aborted write"
        if _spoken_id(reply, "AC") and "won't" not in r:
            return "FAIL", "filed despite no"
        return "FAIL", "unclear abort"
    if len(reply) > 60:
        return "PARTIAL", "manual review"
    return "FAIL", "short reply"


def append_progress(seq: int, case_id: str, status: str, note: str) -> None:
    row = f"| {seq} | {case_id} | **{status}** | {note} |"
    if not PROGRESS.is_file():
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text("# Access LA Playwright sequential\n\n| Seq | Case | Status | Note |\n|-----|------|--------|------|\n", encoding="utf-8")
    text = PROGRESS.read_text(encoding="utf-8")
    text = text.rstrip() + "\n" + row + "\n"
    PROGRESS.write_text(text, encoding="utf-8")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated JENNY-1..10")
    parser.add_argument(
        "--caller",
        choices=("llm", "regex"),
        default="llm",
        help="Simulated caller: llm (scenario YAML) or regex (TURN_HINTS)",
    )
    args = parser.parse_args()

    if not EMAIL or not PASSWORD:
        print("Missing FLEXAGENTS credentials")
        return 2

    cases = json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]
    if args.ids:
        want = {x.strip() for x in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in want]
    results = []
    seq = 100  # dashboard seq block

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(2)

        for case in cases:
            seq += 1
            cid = case["id"]
            q = case["question"]
            print(f"--- {cid} ---", flush=True)
            page.goto(JENNY_URL, wait_until="networkidle", timeout=90000)
            time.sleep(2)
            ensure_call_started(page)
            send_and_wait(page, q, timeout=35.0)
            if cid == "JENNY-10":
                send_and_wait(page, "No, don't file it.", timeout=20.0)
            elif args.caller == "llm":
                rounds = 20 if cid == "JENNY-7" else 14
                llm_dialogue(page, cid, case.get("pass", ""), max_rounds=rounds)
            else:
                auto_dialogue(page, cid, max_rounds=14 if cid == "JENNY-7" else 10)
                if cid == "JENNY-7":
                    time.sleep(25)
                    auto_dialogue(page, cid, max_rounds=8)
            full = page_transcript(page)
            reply = full if cid == "JENNY-7" else full[-4000:]
            status, note = judge(cid, reply, q)
            results.append(
                {
                    "seq": seq,
                    "id": cid,
                    "question": case["question"],
                    "status": status,
                    "note": note,
                    "reply_snippet": (reply or "")[:1200],
                    "pass_criteria": case["pass"],
                }
            )
            append_progress(seq, f"DASH-{cid}", status, note)
            print(f"{cid} {status}: {note}", flush=True)
            time.sleep(2)

        browser.close()

    out = ROOT / "eval/reports/access_la_playwright_latest.json"
    md = ROOT / "eval/reports/access_la_playwright_latest.md"
    out.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "url": JENNY_URL,
                "caller_mode": args.caller,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    lines = [
        "# Access LA — Playwright (Jenny)",
        "",
        f"**URL:** {JENNY_URL}",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "| ID | Status | Note |",
        "|----|--------|------|",
    ]
    for r in results:
        lines.append(f"| {r['id']} | **{r['status']}** | {r['note'][:100]} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {md}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    print(f"DASHBOARD SUMMARY: PASS={passed} PARTIAL={partial} / {len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())