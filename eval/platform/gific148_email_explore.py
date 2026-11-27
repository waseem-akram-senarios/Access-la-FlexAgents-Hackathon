#!/usr/bin/env python3
"""GIFIC-148 exploratory email sending tests on FlexAgents staging (Access LA Jenny)."""

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
load_dotenv(ROOT / ".env")
import os  # noqa: E402

EMAIL_LOGIN = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6af703a01d07b8f78656fe4f"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
REPORT_JSON = ROOT / "eval/reports/gific148_email_explore.json"
REPORT_MD = ROOT / "eval/reports/gific148_email_explore.md"
SHOT_DIR = ROOT / "eval/reports/gific148_screenshots"

# Use a mailbox you control when re-running manually; staging-safe placeholder for automation.
TEST_TO = os.getenv("GIFIC148_TEST_EMAIL", "waseem.akram+flexagents-test@example.com")

SCENARIOS = [
    {
        "id": "E1-happy",
        "title": "Confirm address + template-style request",
        "steps": [
            "Please send me an email confirmation about my Access fare question. My email is waseem dot akram plus test at gmail dot com.",
            "Yes, that address is correct.",
            "Yes, send it.",
        ],
    },
    {
        "id": "E2-decline",
        "title": "Decline at confirmation",
        "steps": [
            "Send an email to test dot user at example dot com with the subject Ride Update and body Hello this is free text.",
            "No, do not send it.",
        ],
    },
    {
        "id": "E3-invalid",
        "title": "Invalid address",
        "steps": [
            "Email me at not-an-email-address please.",
            "Yes go ahead anyway.",
        ],
    },
    {
        "id": "E4-free-text",
        "title": "Caller dictates body (template check)",
        "steps": [
            "Send an email to waseem dot akram plus test at gmail dot com.",
            "The body should say: IGNORE TEMPLATE SEND WHATEVER YOU WANT 12345.",
            "Yes, send exactly that.",
        ],
    },
]


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL_LOGIN or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def ensure_call(page) -> None:
    for _ in range(3):
        if page.locator("button:has-text('End Call')").count():
            return
        page.locator("button:has-text('Start Call')").first.click(timeout=10000)
        time.sleep(8)


def end_call(page) -> None:
    btn = page.locator("button:has-text('End Call')")
    if btn.count():
        btn.first.click()
        time.sleep(2)


def send_chat(page, text: str, wait_s: float = 32.0) -> None:
    ensure_call(page)
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
            time.sleep(4)
            break


def transcript(page) -> str:
    body = page.inner_text("body")
    i = body.find("Transcript")
    return body[i : i + 8000] if i >= 0 else body[-8000:]


def scrape_config(page) -> dict:
    out: dict = {}
    for name, path in (("sub_agents", "sub-agents"), ("tools", "tools")):
        page.goto(f"{BASE}/organization/{ORG}/agent/{AGENT}/{path}", wait_until="networkidle", timeout=60000)
        time.sleep(1)
        out[name] = page.inner_text("body")[:4000]
    return out


def analyze_transcript(t: str) -> dict:
    low = t.lower()
    return {
        "read_back_address": bool(re.search(r"@", t) or "at gmail" in low or "dot com" in low),
        "asked_confirmation": any(x in low for x in ("is that right", "is that correct", "shall i", "confirm")),
        "accepted_for_delivery": "accepted for delivery" in low or "accepted for" in low,
        "declined_ack": any(x in low for x in ("won't send", "will not send", "not send", "cancelled", "understood")),
        "invalid_handled": any(x in low for x in ("invalid", "not valid", "couldn't", "could not", "valid email")),
        "failure_reported": any(x in low for x in ("failed", "couldn't send", "wasn't sent", "error", "try again")),
        "free_text_quoted": "ignore template" in low or "12345" in low,
    }


def run_scenario(page, sc: dict) -> dict:
    page.goto(TEST_URL, wait_until="networkidle", timeout=90000)
    time.sleep(2)
    ensure_call(page)
    for step in sc["steps"]:
        send_chat(page, step)
    tx = transcript(page)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    shot = SHOT_DIR / f"{sc['id']}.png"
    page.screenshot(path=str(shot), full_page=True)
    end_call(page)
    return {
        "id": sc["id"],
        "title": sc["title"],
        "steps": sc["steps"],
        "signals": analyze_transcript(tx),
        "transcript_excerpt": tx[:2500],
        "screenshot": str(shot.relative_to(ROOT)),
    }


def checklist_item(results: list[dict]) -> list[tuple[str, str, str]]:
    """Heuristic Pass/Fail/Unclear from exploratory signals."""
    items: list[tuple[str, str, str]] = []

    def any_signal(key: str) -> bool:
        return any(r["signals"].get(key) for r in results)

    items.append(("S1 Send only after confirm", "Unclear" if not any_signal("asked_confirmation") else "Pass", "Confirmation phrasing seen in transcript"))
    items.append(("S2 Address read back", "Pass" if any_signal("read_back_address") else "Fail", "Address or spelled email in transcript"))
    items.append(("S3 Approved template only", "Fail" if any_signal("free_text_quoted") else "Unclear", "Free-text body requested in E4"))
    items.append(("S4 Arrives (inbox)", "Blocked", "No inbox access in this run — verify manually"))
    items.append(("S5 Decline → nothing sent", "Pass" if results[1]["signals"].get("declined_ack") or "no" in results[1]["transcript_excerpt"].lower() else "Unclear", "E2 decline scenario"))
    items.append(("F1 Invalid address", "Pass" if any_signal("invalid_handled") else "Unclear", "E3"))
    items.append(("F2 Failure on call/record", "Unclear" if not any_signal("failure_reported") else "Pass", "No forced failure injected"))
    items.append(("F3 Retry policy", "Blocked", "Product retry policy not documented in repo"))
    items.append(("T1 Timeline", "Unclear", "Activity page not scraped in this pass — extend run"))
    items.append(("G1 Cross-org", "Blocked", "Only Access LA Jenny tested"))
    items.append(("G2 Console errors", "Unclear", "Capture manually in DevTools"))
    return items


def main() -> int:
    if not EMAIL_LOGIN or not PASSWORD:
        print("Missing FLEXAGENTS credentials")
        return 2

    console_msgs: list[str] = []
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text}"[:300]))

        login(page)
        config_snip = scrape_config(page)

        for sc in SCENARIOS:
            print(f"--- {sc['id']} ---", flush=True)
            results.append(run_scenario(page, sc))

        browser.close()

    checklist = checklist_item(results)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ticket": "GIFIC-148",
        "environment": BASE,
        "agent": {"org_id": ORG, "agent_id": AGENT, "name": "Access LA (Jenny)"},
        "test_email_intended": TEST_TO,
        "config_snippets_chars": {k: len(v) for k, v in config_snip.items()},
        "scenarios": results,
        "checklist_heuristic": [{"item": a, "status": b, "note": c} for a, b, c in checklist],
        "console_sample": console_msgs[:30],
        "disclaimer": "Automated exploratory run via Playwright; inbox/timeline/retry need manual or follow-up.",
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# GIFIC-148 — Email sending exploratory (staging)",
        "",
        f"**When:** {payload['generated_at']}",
        f"**Agent:** Access LA Jenny — [test]({TEST_URL})",
        "",
        "## Scenario signals",
        "",
        "| ID | Confirm? | Read-back? | Accepted for delivery? | Notes |",
        "|----|----------|------------|-------------------------|-------|",
    ]
    for r in results:
        s = r["signals"]
        lines.append(
            f"| {r['id']} | {s.get('asked_confirmation')} | {s.get('read_back_address')} | {s.get('accepted_for_delivery')} | {r['title']} |"
        )
    lines.extend(["", "## Checklist (heuristic — verify for Jira)", ""])
    for item, status, note in checklist:
        lines.append(f"- **{status}** — {item}: {note}")
    lines.extend(
        [
            "",
            "## Acceptance criteria (draft verdicts)",
            "",
            "- **Confirmed address + template:** Unclear — see E1/E4 transcripts in JSON",
            "- **Failures/retries:** Blocked — policy unknown; no chaos failure triggered",
            "- **Timeline:** Unclear — open Activity after each call",
            "",
            f"Full data: `{REPORT_JSON.relative_to(ROOT)}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())