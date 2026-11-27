#!/usr/bin/env python3
"""Conversation-only email test: Refund Support Agent + Refund Email Assistant."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

USER = os.getenv("FLEXAGENTS_USERNAME")
PASSWD = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b0066ba91c89920b65d5dae"
TEST = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
SUB = f"{BASE}/organization/{ORG}/agent/{AGENT}/sub-agents/ec0466e02df560dec025f6c8"
TOOLS = f"{BASE}/organization/{ORG}/agent/{AGENT}/tools"
TO = "waseem@aidevlab.com"
KEY = os.getenv("MESSAGES_API_KEY", "")
OUT = ROOT / "eval/reports/refund_conversation_email.json"


def outbox_ids() -> set[str]:
    if not KEY:
        return set()
    req = urllib.request.Request(
        f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=20",
        headers={"X-API-Key": KEY},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
        return {e["email_id"] for e in data.get("results") or []}


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', USER or "")
    page.fill('input[type="password"]', PASSWD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def say(page, text: str, wait: float = 38.0) -> str:
    if page.locator("button:has-text('Start Call')").count():
        page.locator("button:has-text('Start Call')").first.click()
        time.sleep(10)
    box = page.locator("input[placeholder='Type a message...']")
    box.wait_for(state="visible", timeout=60000)
    prev = page.inner_text("body")
    box.fill(text)
    time.sleep(0.2)
    page.keyboard.press("Enter")
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(2)
        cur = page.inner_text("body")
        if len(cur) > len(prev) + 90:
            time.sleep(5)
            return cur[-2500:]
    return page.inner_text("body")[-2500:]


def main() -> int:
    before = outbox_ids()
    setup: dict = {}

    script = [
        ("I bought a subscription by mistake. I want a refund confirmation email, not a refund processed yet.", 40),
        (f"The email should go to {TO}.", 40),
        (
            "The email content is: Your refund request is approved for review. "
            "Reference STG-CONV-001. Amount $25.",
            45,
        ),
        ("Yes, send to that address with exactly that content.", 45),
        ("Yes, I confirm. Please send the email now.", 50),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)

        page.goto(TOOLS, wait_until="networkidle", timeout=60000)
        tb = page.inner_text("body")
        setup["tools_count_line"] = next(
            (ln for ln in tb.splitlines() if "Tools & Integrations" in ln or ln.strip().isdigit()),
            "",
        )
        setup["send_email_on_tools_page"] = "send_email" in tb.lower()

        page.goto(SUB, wait_until="networkidle", timeout=60000)
        sb = page.inner_text("body")
        setup["sub_no_connections"] = "No connections are available" in sb
        setup["sub_email_capability"] = "Email sending" in sb

        page.goto(TEST, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        turns = []
        for text, w in script:
            tail = say(page, text, w)
            turns.append({"caller": text, "agent_tail": tail[-600:]})

        full = page.inner_text("body")
        setup["api_calls_in_trace"] = "API calls" in full and "API calls\n1" in full.replace(" ", "")
        # count api in trace section
        if "API calls" in full:
            idx = full.find("API calls")
            setup["trace_snip"] = full[idx : idx + 120]

        setup["turns"] = turns
        setup["full_tail"] = full[-6000:]
        page.screenshot(path=str(ROOT / "eval/reports/refund_conversation_email.png"), full_page=True)
        browser.close()

    after = outbox_ids()
    new = sorted(after - before)
    setup["new_email_ids"] = new
    setup["at"] = datetime.now(timezone.utc).isoformat()
    setup["can_send_via_conversation"] = bool(new)
    setup["why_no_inbox"] = (
        "Staging Team1 /emails stores outbox only; real SMTP to aidevlab.com is not enabled. "
        "Conversation must invoke send_email tool (sub-agent connection required)."
    )

    OUT.write_text(json.dumps(setup, indent=2), encoding="utf-8")
    print("new_email_ids:", new)
    print("send_email on agent:", setup["send_email_on_tools_page"])
    print("sub no connections:", setup["sub_no_connections"])
    print("can_send_via_conversation:", setup["can_send_via_conversation"])
    print(f"Wrote {OUT}")
    return 0 if new else 1


if __name__ == "__main__":
    raise SystemExit(main())