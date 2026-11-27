#!/usr/bin/env python3
"""Send test email via FlexAgents send_email tool 'Send Test Request' UI."""

from __future__ import annotations

import json
import re
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
TOOL_URL = (
    "https://dashboard-staging.flexagents.ai/organization/6aa1562861347fe1a3087d63/"
    "agent/6af703a01d07b8f78656fe4f/tools/3978f096ebd40f6097286eb1"
)
TO = "waseem@aidevlab.com"
OUT = ROOT / "eval/reports/send_email_tool_request.json"


def login(page) -> None:
    page.goto("https://dashboard-staging.flexagents.ai/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def fill_test_body_fields(page, to: str, subject: str, body: str) -> list[str]:
    """Fill TEST BODY fields in order: to, subject, body, ref (FlexAgents send_email)."""
    filled: list[str] = []
    marker = page.locator("text=TEST BODY").first
    marker.scroll_into_view_if_needed(timeout=10000)
    time.sleep(0.5)
    # Inputs immediately under TEST BODY block (small labels to/subject/body/ref)
    section = page.locator("text=TEST BODY").locator("xpath=ancestor::div[1]")
    inputs = section.locator("input:visible, textarea:visible")
    if inputs.count() < 3:
        inputs = page.locator("text=TEST BODY").locator("xpath=following::input").filter(has_not=page.locator("[type=hidden]"))
    values = [to, subject, body, "eval-tool-test"]
    labels = ["to", "subject", "body", "ref"]
    for i, (lab, val) in enumerate(zip(labels, values)):
        if i >= inputs.count():
            break
        inputs.nth(i).fill(val)
        filled.append(f"{lab}={val[:40]}")
    return filled


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("Missing credentials")
        return 2

    result: dict = {"to": TO, "filled": [], "response_text": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        login(page)
        page.goto(TOOL_URL, wait_until="networkidle", timeout=90000)
        time.sleep(3)

        # Idempotency header if present
        for placeholder in ("Idempotency-Key", "idempotency", "Idempotency"):
            loc = page.locator(f"input:near(:text('{placeholder}'), 120)")
            if loc.count():
                loc.first.fill(f"eval-send-{int(time.time())}")
                result["filled"].append("Idempotency-Key")
                break

        result["filled"].extend(
            fill_test_body_fields(
                page,
                TO,
                "FlexAgents staging test",
                "Hello from staging send_email tool test.",
            )
        )

        btn = page.get_by_role("button", name=re.compile(r"Send Test Request", re.I))
        if not btn.count():
            btn = page.locator("button:has-text('Send Test Request')")
        if btn.count():
            btn.first.click()
            time.sleep(8)
            result["steps"] = ["clicked_send_test_request"]
        else:
            result["error"] = "Send Test Request button not found"

        result["response_text"] = page.inner_text("body")[-3500:]
        low = result["response_text"].lower()
        result["success_signals"] = {
            "200": "200" in result["response_text"] or "201" in result["response_text"],
            "success": "success" in low,
            "email_id": "email" in low and "id" in low,
            "error": "error" in low or "failed" in low,
        }
        page.screenshot(path=str(ROOT / "eval/reports/send_email_tool_request.png"), full_page=True)
        browser.close()

    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result.get("success_signals"), indent=2))
    print(f"Filled: {result.get('filled')}")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())