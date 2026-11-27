#!/usr/bin/env python3
"""Try sending a test email via FlexAgents staging tool page + agent chat."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
import os  # noqa: E402

EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
TOOL_URL = (
    f"{BASE}/organization/6aa1562861347fe1a3087d63/agent/"
    f"6af703a01d07b8f78656fe4f/tools/3978f096ebd40f6097286eb1"
)
TEST_URL = f"{BASE}/organization/6aa1562861347fe1a3087d63/agent/6af703a01d07b8f78656fe4f/test"
TO = "waseem@aidevlab.com"
OUT = ROOT / "eval/reports/send_tool_email_result.json"
SHOT = ROOT / "eval/reports/send_tool_email_screenshot.png"


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("Missing FLEXAGENTS credentials")
        return 2

    result: dict = {"tool_url": TOOL_URL, "to": TO, "steps": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        login(page)

        page.goto(TOOL_URL, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        tool_text = page.inner_text("body")
        result["tool_page_title_snip"] = tool_text[:2000]
        result["steps"].append("opened_tool_page")

        # Click any obvious test/send controls on tool page
        for label in ("Test", "Send test", "Try it", "Run", "Execute", "Send"):
            loc = page.get_by_role("button", name=label)
            if loc.count():
                try:
                    loc.first.click(timeout=3000)
                    time.sleep(2)
                    result["steps"].append(f"clicked_button:{label}")
                except Exception:
                    pass

        page.screenshot(path=str(SHOT), full_page=True)

        # Agent test page: explicit simple email request
        page.goto(TEST_URL, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        start = page.locator("button:has-text('Start Call')")
        if start.count():
            start.first.click()
            time.sleep(8)

        prompts = [
            f"Use the email sending tool to send a simple test email to {TO}. "
            "Subject: FlexAgents staging test. Body: Hello from staging tool test.",
            "Yes, that email address is correct.",
            "Yes, send it.",
            "Yes, I confirm.",
        ]
        box = page.locator("input[placeholder='Type a message...']")
        for i, text in enumerate(prompts):
            box.wait_for(state="visible", timeout=45000)
            before = len(page.inner_text("body"))
            box.fill(text)
            time.sleep(0.2)
            page.keyboard.press("Enter")
            t0 = time.time()
            while time.time() - t0 < 45:
                time.sleep(2)
                if len(page.inner_text("body")) > before + 80:
                    time.sleep(5)
                    break
            result["steps"].append(f"chat_{i + 1}")

        transcript = page.inner_text("body")
        low = transcript.lower()
        result["signals"] = {
            "accepted_for_delivery": "accepted for delivery" in low,
            "has_been_sent": "sent" in low and TO.split("@")[0] in low,
            "send_email_mentioned": "email" in low,
            "error": any(x in low for x in ("failed", "error", "couldn't send", "wasn't sent")),
            "confirm_asked": any(x in low for x in ("is that right", "confirm", "correct")),
        }
        result["transcript_tail"] = transcript[-4500:]
        page.screenshot(path=str(ROOT / "eval/reports/send_tool_email_call.png"), full_page=True)
        browser.close()

    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["signals"], indent=2))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())