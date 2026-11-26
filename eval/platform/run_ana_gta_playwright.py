#!/usr/bin/env python3
"""Ana — GTA Playwright suite: GTA 25 Nov issues + N-01..N-14 on FlexAgents staging test page."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
CASES_PATH = ROOT / "eval/scenarios/ana_gta_playwright.json"
REPORT_JSON = ROOT / "eval/reports/ana_gta_playwright_latest.json"
REPORT_MD = ROOT / "eval/reports/ana_gta_playwright_latest.md"
BASE = "https://dashboard-staging.flexagents.ai"


def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def latest_agent_reply(page) -> str:
    """Best-effort: transcript block above the input, else tail of body."""
    for sel in (
        "[data-testid='transcript']",
        "div:has-text('Transcript')",
    ):
        loc = page.locator(sel)
        if loc.count():
            try:
                text = loc.first.inner_text(timeout=2000)
                if text and len(text) > 30:
                    return _extract_agent_tail(text)
            except Exception:
                pass
    body = page.inner_text("body")
    return _extract_agent_tail(body)


def _extract_agent_tail(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks: list[str] = []
    for line in reversed(lines):
        low = line.lower()
        if any(x in low for x in ("type a message", "start call", "listening", "end call")):
            continue
        if line in {"Agent", "You", "User", "Transcript"}:
            continue
        chunks.insert(0, line)
        if len(" ".join(chunks)) > 400:
            break
    return " ".join(chunks[-8:]) if chunks else text[-600:]


def send_message(page, message: str, wait_s: float = 18.0) -> str:
    box = page.locator("input[placeholder='Type a message...']")
    box.wait_for(state="visible", timeout=25000)
    before = latest_agent_reply(page)
    box.fill(message)
    time.sleep(0.25)
    page.keyboard.press("Enter")
    deadline = time.time() + wait_s
    last = before
    while time.time() < deadline:
        time.sleep(2.0)
        cur = latest_agent_reply(page)
        if cur != before and len(cur) > len(before) + 15:
            last = cur
            break
        last = cur
    return last


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def start_call(page) -> None:
    page.locator("button:has-text('Start Call')").first.click(timeout=15000)
    time.sleep(7)


def judge(case_id: str, transcript: str, steps: list[str]) -> tuple[str, str]:
    t = transcript.lower()
    if len(transcript.strip()) < 25:
        return "FAIL", "no/minimal agent text in transcript"

    if case_id == "GTA-1":
        if re.search(r"26\s+(november|nov)", t) or "november 26" in t:
            if re.search(r"25\s+(november|nov)", t) and "book" in t and "26" not in t:
                return "FAIL", "booked or confirmed wrong day (25 only)"
            return "PASS", "full date / tomorrow acknowledged"
        if "wrong" in t or re.search(r"november\s+2[0-4]", t):
            return "FAIL", "wrong date language"
        return "PARTIAL", "date not clearly repeated — manual review"

    if case_id == "GTA-2":
        if "have all the detail" in t or "already have" in t:
            return "PASS", "acknowledged details; moved on (e.g. name)"
        reask_phrases = ("what time", "pickup address", "drop-off address", "how many passenger")
        if sum(1 for p in reask_phrases if p in t) >= 2:
            return "FAIL", "re-asked booking fields"
        if "confirmation" in t or re.search(r"ana-\d+", transcript, re.I):
            return "PASS", "progressed toward booking"
        return "PARTIAL", "may be asking name/next step — review transcript"

    if case_id == "GTA-3":
        if "cannot help" in t and "service" not in t and "hour" not in t:
            return "FAIL", "generic cannot help"
        if "service hour" in t or "outside" in t or "available" in t or "6 am" in t:
            return "PASS", "explained hours or availability"
        return "PARTIAL", "manual review"

    if case_id == "GTA-4":
        id_asks = len(re.findall(r"client id|rider id", t))
        if id_asks >= 3:
            return "FAIL", "repeated client/rider ID (GTA-4 baseline)"
        if re.search(r"ana-\d+", transcript, re.I) or "booked" in t or "confirmation" in t:
            return "PASS", "booking completed"
        if "name" in t and id_asks <= 1:
            return "PARTIAL", "stalled on name — not client ID loop (re-test)"
        if id_asks >= 1 and "book" not in t:
            return "FAIL", "rider/client ID blocked booking"
        return "PARTIAL", "did not reach confirmation — review transcript"

    if case_id == "N-01":
        if ("dart" in t or "access" in t) and "profile" not in t[:200].lower():
            return "FAIL", "asked service before lookup line"
        if "no profile" in t or "not found" in t:
            if "dart" in t or "access" in t:
                return "PASS", "lookup then DART/ACCESS"
        if "dart" in t and "0140" in " ".join(steps):
            return "PARTIAL", "order unclear — manual"
        return "FAIL", "missing no-profile + service ask"

    if case_id == "N-02":
        if "r-55" in t or "rider id" in t:
            if "eligib" in t or "2 pm" in t or "book" in t:
                return "PASS", "rider ID path"
            return "PARTIAL", "asked ID — eligibility unclear"
        return "FAIL", "skipped rider ID"

    if case_id == "N-03":
        if re.search(r"card|cash|payment|pay with", t):
            return "FAIL", "asked payment on zero fare"
        if re.search(r"ana-\d+", transcript, re.I) or "confirm" in t:
            return "PASS", "completed without payment"
        if "end" in t and len(t) < 80:
            return "FAIL", "call ended early (sim baseline)"
        return "PARTIAL", "no confirmation captured"

    if case_id == "N-04":
        if "main street" in t and ("clinic" in t or "library" in t):
            return "PASS", "offered Main Street choices"
        if "could not find" in t:
            return "FAIL", "no match / no disambiguation"
        return "PARTIAL", "manual"

    if case_id == "N-05":
        if "cancel" in t and re.search(r"ana-1001|1001", transcript, re.I):
            return "PASS", "cancelled or addressed ANA-1001"
        if "which" in t and "ride" in t:
            return "FAIL", "asked which ride"
        return "PARTIAL", "cancel outcome unclear"

    if case_id == "N-06":
        if "transfer" in t and "rider id" in t:
            return "PARTIAL", "baseline: stop + transfer offer"
        if "book" in t and "cannot" not in t:
            return "PASS", "unexpected pass: booked without ID"
        if "requires a rider id" in t or "rider id" in t:
            return "FAIL", "baseline: hard stop without book"
        return "PARTIAL", "manual"

    if case_id == "N-07":
        if "a17" in t or "does not exist" in t or "not exist" in t:
            if "a17" in steps[-1].lower() and ("eligib" in t or "book" in t):
                return "PASS", "accepted A17"
            return "FAIL", "rejection or bad parse (817/R55 baseline)"
        return "PARTIAL", "manual"

    if case_id == "N-08":
        if "cannot" in t and "rider id" in t:
            return "FAIL", "baseline: required rider ID for status"
        if re.search(r"ana-\d+|2:00|library|clinic|pickup", t):
            return "PASS", "ride status without rider ID"
        return "PARTIAL", "manual"

    if case_id == "N-09":
        if "cannot create" in t or "can't create" in t:
            if "transfer" in t:
                return "PASS", "honest + transfer path"
            return "PARTIAL", "honest dead-end (baseline)"
        return "FAIL", "did not refuse create-ID"

    if case_id == "N-10":
        if "could not find a match" in t and "library" not in t:
            return "FAIL", "baseline geocode fail"
        if "library" in t or "moses" in t or "which" in t:
            return "PASS", "disambiguation or library list"
        return "PARTIAL", "manual"

    if case_id == "N-11":
        if "not found" in t and "cancel" in t:
            return "PARTIAL", "baseline not-found (staging data)"
        if "cancel" in t and "1001" in transcript:
            return "PASS", "cancelled"
        return "PARTIAL", "manual"

    if case_id == "N-12":
        if "guess" in t or "sanaullah" in t:
            return "FAIL", "wrong name / guessed"
        if "jamie" in t or "your name" in t or "name" in t:
            return "PASS", "name flow"
        return "PARTIAL", "manual"

    if case_id == "N-13":
        if "same day" in t or "same-day" in t:
            return "PARTIAL", "baseline: same-day refused (verify policy)"
        if re.search(r"ana-\d+", transcript, re.I):
            return "PASS", "same-day booked"
        return "PARTIAL", "manual"

    if case_id == "N-14":
        if t.count("outside") >= 2 and "service hour" in t:
            return "FAIL", "baseline: all times rejected"
        if "2 pm" in t and ("inside" in t or "available" in t or "book" in t):
            return "PASS", "accepted or explained 2 PM"
        return "PARTIAL", "manual"

    if len(transcript) > 80:
        return "PARTIAL", "no automated rule — manual review"
    return "FAIL", "short transcript"


def write_markdown(meta: dict, results: list[dict]) -> None:
    lines = [
        "# Ana — GTA Playwright run",
        "",
        f"**Generated:** {meta['generated_at']}",
        f"**URL:** {meta['url']}",
        "",
        "| ID | Title | Baseline | Result | Note |",
        "|----|-------|----------|--------|------|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['title']} | {r.get('baseline', '')} | **{r['status']}** | {r['note'][:120]} |"
        )
    lines.extend(["", "## Regression", ""])
    fixed = [r["id"] for r in results if r.get("baseline") == "fail" and r["status"] == "PASS"]
    open_ = [r["id"] for r in results if r.get("baseline") == "fail" and r["status"] == "FAIL"]
    lines.append(f"- Fixed vs baseline: {', '.join(fixed) or '—'}")
    lines.append(f"- Still failing: {', '.join(open_) or '—'}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated case ids (e.g. GTA-1,N-01)")
    parser.add_argument("--group", choices=["gta_25nov", "qa_matrix"], help="Run one group only")
    parser.add_argument("--wait", type=float, default=20.0, help="Seconds wait per step")
    args = parser.parse_args()

    if not EMAIL or not PASSWORD:
        print("Set FLEXAGENTS_USERNAME and FLEXAGENTS_PASSWORD in .env", file=sys.stderr)
        return 2

    spec = load_cases()
    url = spec["dashboard_test_url"]
    cases = spec["cases"]
    if args.group:
        cases = [c for c in cases if c.get("group") == args.group]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if not cases:
        print("No cases selected", file=sys.stderr)
        return 2

    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
            ],
        )
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        login(page)

        for case in cases:
            cid = case["id"]
            print(f"=== {cid} {case['title']} ===", flush=True)
            row = {
                "id": cid,
                "title": case["title"],
                "baseline": case.get("baseline"),
                "session_ref": case.get("session_ref"),
                "evidence": case.get("evidence"),
                "status": "FAIL",
                "note": "",
                "transcript_tail": "",
                "steps": case["steps"],
            }
            try:
                page.goto(url, wait_until="networkidle", timeout=90000)
                time.sleep(2)
                if page.locator("button:has-text('Start Call')").count():
                    start_call(page)
                transcript_parts: list[str] = []
                for step in case["steps"]:
                    reply = send_message(page, step, wait_s=args.wait)
                    transcript_parts.append(f"USER: {step}\nAGENT: {reply}")
                full = "\n".join(transcript_parts)
                tail = latest_agent_reply(page)
                status, note = judge(cid, full + "\n" + tail, case["steps"])
                row["status"] = status
                row["note"] = note
                row["transcript_tail"] = (tail or full)[-1200:]
            except Exception as exc:  # noqa: BLE001
                row["note"] = str(exc)[:240]
                row["status"] = "ERROR"
            results.append(row)
            print(f"{cid} {row['status']}: {row['note']}", flush=True)
            time.sleep(2)

        browser.close()

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "reference_today": spec.get("reference_today"),
        "case_count": len(results),
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({"meta": meta, "results": results}, indent=2), encoding="utf-8")
    write_markdown(meta, results)
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    print(f"SUMMARY: PASS={passed} PARTIAL={partial} FAIL/ERROR={failed} / {len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())