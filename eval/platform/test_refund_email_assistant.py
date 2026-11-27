#!/usr/bin/env python3
"""Test Refund Email Assistant sub-agent on FlexAgents staging."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

EMAIL_LOGIN = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b0066ba91c89920b65d5dae"
SUBAGENT = "ec0466e02df560dec025f6c8"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
SUB_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/sub-agents/{SUBAGENT}"
TO = "waseem@aidevlab.com"
REPORT = ROOT / "eval/reports/refund_email_assistant_test.json"
MESSAGES_KEY = os.getenv("MESSAGES_API_KEY", "")


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL_LOGIN or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def send_chat(page, text: str, wait_s: float = 40.0) -> None:
    if page.locator("button:has-text('Start Call')").count():
        page.locator("button:has-text('Start Call')").first.click()
        time.sleep(8)
    box = page.locator("input[placeholder='Type a message...']")
    box.wait_for(state="visible", timeout=45000)
    before = len(page.inner_text("body"))
    box.fill(text)
    time.sleep(0.2)
    page.keyboard.press("Enter")
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(2)
        if len(page.inner_text("body")) > before + 100:
            time.sleep(5)
            break


def transcript(page) -> str:
    body = page.inner_text("body")
    i = body.find("Transcript")
    return body[i : i + 12000] if i >= 0 else body[-12000:]


def outbox_count() -> dict:
    if not MESSAGES_KEY:
        return {"error": "no MESSAGES_API_KEY"}
    url = f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=3"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "X-API-Key": MESSAGES_KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
            return {"count": data.get("count"), "latest": (data.get("results") or [])[:3]}
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read()[:200]}


def analyze(tx: str) -> dict:
    low = tx.lower()
    return {
        "confirm_asked": bool(re.search(r"confirm|is that right|shall i|read back", low)),
        "email_mentioned": "email" in low,
        "accepted_for_delivery": "accepted for delivery" in low or "accepted for" in low,
        "sent_ok": any(x in low for x in ("sent", "delivered", "on its way", "email has been")),
        "refused_or_no_send": "won't send" in low or "will not send" in low or "won't send" in low,
        "subagent_trace": "refund" in low or "sub-agent" in low or "send_email" in low,
        "api_calls_in_trace": "api calls" in low and re.search(r"api calls\s*\n\s*[1-9]", low) is not None,
    }


def main() -> int:
    if not EMAIL_LOGIN or not PASSWORD:
        print("Missing FLEXAGENTS credentials")
        return 2

    result: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_agent_url": SUB_URL,
        "test_url": TEST_URL,
        "to": TO,
    }

    before_outbox = outbox_count()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)

        page.goto(SUB_URL, wait_until="networkidle", timeout=90000)
        time.sleep(2)
        sub_text = page.inner_text("body")[:2500]
        result["sub_agent_snip"] = sub_text
        result["sub_agent_active"] = "Refund Email" in sub_text or "refund" in sub_text.lower()

        page.goto(TEST_URL, wait_until="networkidle", timeout=90000)
        time.sleep(2)

        flow = [
            "I need a refund confirmation email sent to waseem@aidevlab.com. "
            "The message should say: Your refund of $25 has been approved. Reference REF-TEST-001.",
            "Yes, that email address and message are correct. Please send it.",
            "Yes, I confirm. Send the email now.",
        ]
        for i, line in enumerate(flow):
            send_chat(page, line)
            result.setdefault("steps", []).append(f"turn_{i + 1}")

        tx = transcript(page)
        result["signals"] = analyze(tx)
        result["transcript_excerpt"] = tx[:4000]
        page.screenshot(path=str(ROOT / "eval/reports/refund_email_assistant.png"), full_page=True)
        browser.close()

    after_outbox = outbox_count()
    result["outbox_before"] = before_outbox
    result["outbox_after"] = after_outbox

    before_ids = {e.get("email_id") for e in (before_outbox.get("latest") or []) if isinstance(before_outbox, dict)}
    after_list = after_outbox.get("latest") or [] if isinstance(after_outbox, dict) else []
    new_emails = [e for e in after_list if e.get("email_id") not in before_ids]
    result["new_outbox_emails"] = new_emails
    result["verdict"] = (
        "PASS outbox"
        if new_emails
        else ("PARTIAL transcript" if result["signals"].get("sent_ok") or result["signals"].get("accepted_for_delivery") else "FAIL no send")
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Verdict: {result['verdict']}")
    print(json.dumps(result["signals"], indent=2))
    print(f"New outbox: {new_emails}")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())