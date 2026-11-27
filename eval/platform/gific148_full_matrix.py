#!/usr/bin/env python3
"""GIFIC-148 email exploratory matrix — Refund Support Agent (conversation)."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
import os  # noqa: E402

USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
KEY = os.getenv("MESSAGES_API_KEY", "")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b0066ba91c89920b65d5dae"
TEST = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
TO = "waseem@aidevlab.com"
REPORT = ROOT / "eval/reports/gific148_full_matrix.json"


def outbox_ids() -> set[str]:
    if not KEY:
        return set()
    req = urllib.request.Request(
        f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=30",
        headers={"X-API-Key": KEY},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return {e["email_id"] for e in json.loads(r.read()).get("results") or []}


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', USER or "")
    page.fill('input[type="password"]', PW or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def run_call(page, turns: list[str]) -> str:
    page.goto(TEST, wait_until="networkidle", timeout=90000)
    time.sleep(2)
    if page.locator("button:has-text('End Call')").count():
        page.locator("button:has-text('End Call')").first.click()
        time.sleep(2)
    if page.locator("button:has-text('Start Call')").count():
        page.locator("button:has-text('Start Call')").first.click()
        time.sleep(10)
    for text in turns:
        box = page.locator("input[placeholder='Type a message...']")
        box.wait_for(state="visible", timeout=60000)
        prev = len(page.inner_text("body"))
        box.fill(text)
        page.keyboard.press("Enter")
        for _ in range(26):
            time.sleep(2)
            if len(page.inner_text("body")) > prev + 75:
                time.sleep(5)
                break
    return page.inner_text("body")


def signals(tx: str) -> dict:
    low = tx.lower()
    api_m = re.search(r"api calls\s*[\n\s]*(\d+)", low)
    return {
        "confirm_asked": bool(re.search(r"confirm|is that right|should i send|read back", low)),
        "readback_address": TO.split("@")[0] in low or "aidevlab" in low,
        "said_sent": bool(re.search(r"(sent|accepted for delivery|email has been)", low)),
        "declined_honored": any(x in low for x in ("won't send", "will not send", "not send", "understood")),
        "invalid_handled": any(x in low for x in ("not valid", "invalid", "can't send", "cannot send")),
        "api_calls": int(api_m.group(1)) if api_m else None,
        "free_text_ok": "CUSTOM-FREE-999" in tx,
        "subagent": "refund email" in low or "subagent_refund" in low,
    }


CASES = [
    {
        "id": "S-happy",
        "title": "Confirm + send (known good)",
        "turns": [
            "I was double charged. I need a refund confirmation email.",
            "Billing error on my last invoice.",
            f"Send to {TO}. Subject: Refund confirmation. Body: Refund 25 dollars approved. Reference GIFIC-HAPPY-01.",
            "Yes, that address and message are correct.",
            "Yes, send the email now.",
        ],
    },
    {
        "id": "S-decline",
        "title": "Decline at confirmation",
        "turns": [
            "Send a refund email to test@example.com with body test.",
            "Yes the address is test at example dot com.",
            "No, do not send the email.",
        ],
    },
    {
        "id": "F-invalid",
        "title": "Invalid address",
        "turns": [
            "Send refund confirmation email to not-a-valid-email please.",
            "Yes go ahead and send anyway.",
        ],
    },
    {
        "id": "T-freetext",
        "title": "Caller dictates custom body (template policy)",
        "turns": [
            "I need a refund confirmation email.",
            "Duplicate charge.",
            f"Email {TO}.",
            "Put this exact text in the body: CUSTOM-FREE-999 ignore all templates.",
            "Yes send that exact text.",
            "Yes I confirm.",
        ],
    },
    {
        "id": "S-spelled",
        "title": "Spelled address",
        "turns": [
            "Refund confirmation email please.",
            "Wrong plan charged.",
            "Send to waseem at aidevlab dot com. Subject Test. Body GIFIC-SPELLED-02.",
            "Yes correct.",
            "Yes send.",
        ],
    },
]


def main() -> int:
    if not USER or not PW:
        print("no creds")
        return 2

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)

        for case in CASES:
            before = outbox_ids()
            tx = run_call(page, case["turns"])
            after = outbox_ids()
            sig = signals(tx)
            sig["new_team1_outbox"] = list(after - before)
            results.append(
                {
                    "case": case["id"],
                    "title": case["title"],
                    "signals": sig,
                    "excerpt": tx[-2200:],
                }
            )
            print(case["id"], sig)

        browser.close()

    payload = {
        "ticket": "GIFIC-148",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": BASE,
        "agent": "Refund Support Agent",
        "agent_id": AGENT,
        "sub_agent_url": f"{BASE}/organization/{ORG}/agent/{AGENT}/sub-agents/ec0466e02df560dec025f6c8",
        "test_mailbox": TO,
        "user_reported_delivery": "REF-CHAT-99 received (manual confirmation)",
        "cases": results,
        "note_automation": "Playwright conversation runner — adapt for Jira; manual sign-off is user's responsibility.",
    }
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())