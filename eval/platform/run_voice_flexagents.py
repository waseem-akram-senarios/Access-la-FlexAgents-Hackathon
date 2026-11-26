#!/usr/bin/env python3
"""Platform voice-ish tests via FlexAgents staging test page (WebRTC + optional text)."""

from __future__ import annotations

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
BASE = "https://dashboard-staging.flexagents.ai"

# Platform-focused prompts (English only — watch for P-01)
AGENTS = {
    "neo": f"{BASE}/organization/6af72a3c4431b640e6041707/agent/6af72aab4431b640e6041709/test",
    "jenny": f"{BASE}/organization/6aa1562861347fe1a3087d63/agent/6af703a01d07b8f78656fe4f/test",
}

TESTS = [
    ("V-N1", "neo", "Does Route 1 stop at Knight Street Transit Center?", "yes|stop|route 1", "P-04/P-05"),
    (
        "V-N2",
        "neo",
        "Is my Route 1 bus at Knight Street running late?",
        "late|2:35|2:42|minute|scheduled|predicted",
        "P-05",
    ),
    ("V-J1", "jenny", "Who do I call if I left my bag on the bus? Is that department open?", "lost|213|open|closed", "P-01/orchestration"),
]


def send_and_wait(page, question: str, timeout: float = 45.0) -> str:
    input_box = page.locator("input[placeholder='Type a message...']")
    input_box.wait_for(state="visible", timeout=15000)
    input_box.fill(question)
    time.sleep(0.3)
    page.keyboard.press("Enter")
    time.sleep(timeout)
    # Collect text after the user question (avoid matching UI labels)
    body = page.inner_text("body")
    idx = body.find(question[:40])
    if idx >= 0:
        return body[idx + len(question) : idx + len(question) + 800].strip()
    return body[-800:].strip()


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("Missing FLEXAGENTS_USERNAME or FLEXAGENTS_PASSWORD in .env")
        return 2

    results = []
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
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(2)

        for test_id, agent_key, question, expect_pattern, pids in TESTS:
            url = AGENTS[agent_key]
            row = {
                "id": test_id,
                "platform": pids,
                "agent": agent_key,
                "question": question,
                "status": "fail",
                "reply_snippet": "",
                "note": "",
            }
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(3)
                start = page.locator("button:has-text('Start Call')")
                if start.count() > 0:
                    start.first.click()
                    time.sleep(8)
                reply = send_and_wait(page, question)
                row["reply_snippet"] = (reply or "")[:400]
                fail_markers = ("trouble finding", "unable to locate", "cannot find", "system error")
                if any(m in reply.lower() for m in fail_markers):
                    row["status"] = "fail"
                    row["note"] = "stop/GTFS lookup failure in reply"
                elif reply and re.search(expect_pattern, reply, re.I) and len(reply) > 40:
                    row["status"] = "pass"
                elif reply:
                    row["note"] = f"reply too short or no match for /{expect_pattern}/"
                else:
                    row["note"] = "no agent reply within timeout"
            except Exception as exc:  # noqa: BLE001
                row["note"] = str(exc)[:200]
            results.append(row)
            print(f"{test_id} {row['status']}: {row['note'] or row['reply_snippet'][:80]}")

        browser.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "flexagents_test_page_webRTC",
        "note": "Start Call enables voice path; prompts sent via chat input (voice STT not asserted here).",
        "results": results,
    }
    out = ROOT / "eval" / "reports" / "platform_voice_latest.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    passed = sum(1 for r in results if r["status"] == "pass")
    print(f"SUMMARY: {passed}/{len(results)} pass")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())