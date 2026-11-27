#!/usr/bin/env python3
"""GIFIC-148 email exploratory — Waseem QA Platform | Staging agent."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gific152_multilingual import ensure_call_started, login, say, wait_text_ready  # noqa: E402

load_dotenv(ROOT / ".env")
import os  # noqa: E402

USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
TO = os.getenv("GIFIC148_TEST_TO", "waseem@aidevlab.com")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b095a096bf2d249020d06bd"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LOG_DIR = ROOT / "eval/reports/gific148_waseem_qa_logs" / TS


def parse_trace(body: str) -> dict:
    low = body.lower()
    m_api = re.search(r"api calls\s*(\d+)", low)
    return {
        "api_calls": int(m_api.group(1)) if m_api else None,
        "confirm": bool(re.search(r"confirm|should i send|is that (right|correct)", low)),
        "readback_email": TO.split("@")[0] in low or "aidevlab" in low,
        "declined": any(x in low for x in ("won't send", "will not send", "not send")),
        "said_sent": bool(re.search(r"sent|accepted for delivery|email has been", low)),
        "cannot_email": any(x in low for x in ("can't send", "cannot send", "no email", "do not transfer")),
        "subagent_email": any(
            x in low
            for x in ("email sending", "email assistant", "subagent", "help you with that email")
        ),
        "invalid_handled": any(x in low for x in ("not valid", "invalid", "isn't a valid")),
    }


def fresh_session(page) -> bool:
    page.goto(TEST_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    if page.locator("button:has-text('Text')").count():
        page.locator("button:has-text('Text')").first.click()
        time.sleep(0.5)
    end = page.locator("button:has-text('End Session'), button:has-text('End Call')")
    if end.count():
        try:
            end.first.click(timeout=3000)
            time.sleep(2)
        except Exception:
            pass
    return ensure_call_started(page) and wait_text_ready(page, 50)


CASES = [
    {
        "id": "E01_happy",
        "desc": "Refund-style happy path email",
        "turns": [
            "I need a test confirmation email sent for GIFIC-148 QA.",
            f"Send to {TO}. Subject: QA Email Test. Body: GIFIC-148-WASEEM-01.",
            "Yes, that address is correct.",
            "Yes, send it now.",
        ],
    },
    {
        "id": "E02_decline",
        "desc": "Decline at confirmation",
        "turns": [
            f"Please email me at {TO} with body DECLINE-TEST.",
            "Yes address is right.",
            "No, do not send the email.",
        ],
    },
    {
        "id": "E03_invalid",
        "desc": "Invalid email address",
        "turns": [
            "Send test email to not-a-valid-email-address please.",
            "Yes go ahead anyway.",
        ],
    },
]


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    master: dict = {
        "ticket": "GIFIC-148",
        "agent": "Waseem QA Platform | Staging",
        "agent_id": AGENT,
        "test_url": TEST_URL,
        "mailbox": TO,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "setup_note": "Waseem QA: Email sending + Knowledge search sub-agents; see waseem_qa_subagents_test.py",
        "cases": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)
        for path in ("sub-agents", "tools"):
            page.goto(f"{BASE}/organization/{ORG}/agent/{AGENT}/{path}", wait_until="domcontentloaded")
            time.sleep(5)
            t = page.inner_text("body")
            master["setup_" + path] = {
                "no_subagents": "No sub-agents yet" in t,
                "qa_email_listed": "QA Email" in t,
                "tools_count_snip": t[t.find("Tools"): t.find("Tools") + 200] if "Tools" in t else "",
            }
            page.screenshot(path=str(LOG_DIR / f"setup_{path}.png"), full_page=True)

        for case in CASES:
            row = {"id": case["id"], "description": case["desc"], "session_ok": False, "turns": []}
            if not fresh_session(page):
                row["error"] = "session_failed"
                master["cases"].append(row)
                continue
            row["session_ok"] = True
            body = ""
            for utterance in case["turns"]:
                t0 = time.time()
                body = say(page, utterance)
                tail = body[max(0, body.rfind("Agent")) :][:600]
                row["turns"].append(
                    {
                        "caller": utterance,
                        "elapsed_s": round(time.time() - t0, 2),
                        "agent_tail": tail,
                    }
                )
            row["trace"] = parse_trace(body)
            row["transcript"] = body[body.find("Transcript") : body.find("Transcript") + 10000] if "Transcript" in body else ""
            page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
            master["cases"].append(row)
            print(case["id"], row["trace"])

        browser.close()

    (LOG_DIR / "MASTER.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print(f"Wrote {LOG_DIR / 'MASTER.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())