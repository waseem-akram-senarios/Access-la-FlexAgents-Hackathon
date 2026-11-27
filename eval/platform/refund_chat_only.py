#!/usr/bin/env python3
"""Refund Support Agent — chat-only email attempt (no tool UI)."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
ROOT = Path(__file__).resolve().parents[2]
USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
KEY = os.getenv("MESSAGES_API_KEY", "")
TEST = (
    "https://dashboard-staging.flexagents.ai/organization/"
    "6aa1562861347fe1a3087d63/agent/6b0066ba91c89920b65d5dae/test"
)
TO = "waseem@aidevlab.com"


def outbox() -> list[dict]:
    if not KEY:
        return []
    with urllib.request.urlopen(
        urllib.request.Request(
            f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=5",
            headers={"X-API-Key": KEY},
        ),
        timeout=20,
    ) as r:
        return json.loads(r.read().decode()).get("results", [])


def say(page, text: str) -> None:
    if page.locator("button:has-text('Start Call')").count():
        page.locator("button:has-text('Start Call')").first.click()
        time.sleep(10)
    b = page.locator("input[placeholder='Type a message...']")
    b.wait_for(state="visible", timeout=60000)
    prev = len(page.inner_text("body"))
    b.fill(text)
    page.keyboard.press("Enter")
    for _ in range(28):
        time.sleep(2)
        if len(page.inner_text("body")) > prev + 85:
            time.sleep(6)
            return


def main() -> None:
    before = {e["email_id"] for e in outbox()}
    script = [
        "Hi Alex. I was charged twice. I need a refund confirmation email only.",
        "Because I was billed twice for the same month.",
        f"Please send the refund confirmation email to {TO}.",
        "Subject: Refund confirmation. Body: Your refund of 25 dollars is approved. Reference REF-CHAT-99.",
        "Yes, that is the correct email address.",
        "Yes, that is the correct subject and body.",
        "Yes, send the email now.",
        "Yes, I confirm.",
    ]
    with sync_playwright() as p:
        br = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = br.new_context(permissions=["microphone"]).new_page()
        page.goto("https://dashboard-staging.flexagents.ai/login", wait_until="networkidle")
        page.fill('input[type="email"]', USER or "")
        page.fill('input[type="password"]', PW or "")
        page.click('button[type=submit]')
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.goto(TEST, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        for line in script:
            say(page, line)
        tail = page.inner_text("body")[-7000:]
        br.close()

    after = outbox()
    new = [e for e in after if e["email_id"] not in before]
    out = {
        "new_outbox_emails": new,
        "said_sent": "sent" in tail.lower() and "email" in tail.lower(),
        "trace_has_api": "API calls" in tail and "API calls\n0" not in tail.replace(" ", ""),
        "transcript_tail": tail[-3500:],
    }
    path = ROOT / "eval/reports/refund_chat_only.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("NEW OUTBOX:", new)
    print("Agent claimed sent:", out["said_sent"])
    print("Wrote", path)


if __name__ == "__main__":
    main()