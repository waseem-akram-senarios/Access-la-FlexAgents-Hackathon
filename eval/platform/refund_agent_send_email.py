#!/usr/bin/env python3
"""Try to send test email via Refund Support Agent + Refund Email Assistant sub-agent."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

USER = os.getenv("FLEXAGENTS_USERNAME")
PASS = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b0066ba91c89920b65d5dae"
TEST = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
TOOLS = f"{BASE}/organization/{ORG}/agent/{AGENT}/tools"
TO = "waseem@aidevlab.com"
OUT = ROOT / "eval/reports/refund_agent_send_attempt.json"
API_KEY = os.getenv("MESSAGES_API_KEY", "")


def outbox_latest() -> list[dict]:
    if not API_KEY:
        return []
    req = urllib.request.Request(
        f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=5",
        headers={"X-API-Key": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("results") or []


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', USER or "")
    page.fill('input[type="password"]', PASS or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def start_call(page) -> None:
    for _ in range(3):
        if page.locator("button:has-text('End Call')").count():
            return
        if page.locator("button:has-text('Start Call')").count():
            page.locator("button:has-text('Start Call')").first.click()
            time.sleep(10)


def chat(page, text: str) -> None:
    start_call(page)
    box = page.locator("input[placeholder='Type a message...']")
    box.wait_for(state="visible", timeout=60000)
    before = page.inner_text("body")
    box.fill(text)
    time.sleep(0.3)
    page.keyboard.press("Enter")
    for _ in range(25):
        time.sleep(2)
        now = page.inner_text("body")
        if len(now) > len(before) + 80:
            time.sleep(6)
            return


def main() -> int:
    if not USER or not PASS:
        print("Missing credentials")
        return 2

    before = outbox_latest()
    before_ids = {x.get("email_id") for x in before}

    lines = [
        "I want a refund confirmation email.",
        f"Send it to {TO}.",
        "The email body should say: Staging test from Refund Email Assistant. Refund $25 approved. Ref STG-001.",
        "Yes, that recipient and exact message are correct.",
        "Yes, I confirm. Please send the email now.",
    ]

    result: dict = {"at": datetime.now(timezone.utc).isoformat(), "turns": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)

        page.goto(TOOLS, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        tools_body = page.inner_text("body")
        result["has_send_email_tool"] = "send_email" in tools_body.lower()
        result["tools_snip"] = tools_body[tools_body.find("Tools") :][:1500] if "Tools" in tools_body else tools_body[:800]

        page.goto(TEST, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        start_call(page)

        tail = ""
        for line in lines:
            chat(page, line)
            tail = page.inner_text("body")[-5000:]
            result["turns"].append({"said": line, "tail": tail[-800:]})

        result["transcript_tail"] = page.inner_text("body")[-8000:]
        page.screenshot(path=str(ROOT / "eval/reports/refund_agent_send.png"), full_page=True)
        browser.close()

    after = outbox_latest()
    new = [e for e in after if e.get("email_id") not in before_ids]
    result["new_outbox"] = new
    result["agent_claimed_sent"] = "sent" in result["transcript_tail"].lower() and TO.split("@")[0] in result["transcript_tail"].lower()
    result["ok"] = bool(new)

    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if new:
        print("SUCCESS — new outbox email:", new[0].get("email_id"), new[0].get("subject"))
    else:
        print("NO outbox record — agent may have claimed send without API.")
        print("has_send_email_tool on parent:", result.get("has_send_email_tool"))
    print(f"Wrote {OUT}")
    return 0 if new else 1


if __name__ == "__main__":
    raise SystemExit(main())