#!/usr/bin/env python3
"""GIFIC-148 in-depth email testing with full logs (Refund Support Agent)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
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
SUB = "ec0466e02df560dec025f6c8"
TO = "waseem@aidevlab.com"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LOG_DIR = ROOT / "eval/reports/gific148_indepth_logs" / TS


def ensure_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(name: str, data: object) -> Path:
    p = LOG_DIR / name
    if isinstance(data, (dict, list)):
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        p.write_text(str(data), encoding="utf-8")
    return p


def fetch_outbox() -> dict:
    if not KEY:
        return {"error": "MESSAGES_API_KEY not set"}
    url = f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=25"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "X-API-Key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read()[:500].decode()}


def parse_trace(body: str) -> dict:
    low = body.lower()
    m_api = re.search(r"api calls\s*(\d+)", low)
    m_sub = re.search(r"agent and sub-agents\s*(\d+)", low)
    m_err = re.search(r"errors\s*(\d+)", low)
    return {
        "api_calls": int(m_api.group(1)) if m_api else None,
        "subagent_actions": int(m_sub.group(1)) if m_sub else None,
        "errors_count": int(m_err.group(1)) if m_err else None,
        "subagent_refund_email": "subagent_refund_email" in low,
        "handoff": "refund email assistant" in low,
        "confirm_phrases": bool(re.search(r"confirm|should i send|is that right", low)),
        "accepted_for_delivery": "accepted for delivery" in low,
        "said_sent": bool(re.search(r"\bsent\b.*email|email.*\bsent\b|has been sent", low)),
        "wont_send": any(x in low for x in ("won't send", "will not send", "not send it")),
        "invalid_msg": any(x in low for x in ("not valid", "invalid email", "isn't a valid")),
    }


CASES = [
    {
        "id": "01_happy_full",
        "desc": "Full refund context + confirm send",
        "turns": [
            "Hello Alex. I was charged twice on my subscription. I need a refund confirmation email only.",
            "It was a duplicate charge on November billing.",
            f"Recipient is {TO}. Subject: Refund confirmation. Body: Your refund of 25 dollars is approved. Reference GIFIC-INDEPTH-01.",
            "Yes, that email address is correct.",
            "Yes, that subject and body are correct.",
            "Yes, please send the email now.",
        ],
    },
    {
        "id": "02_decline",
        "desc": "Caller declines at confirmation",
        "turns": [
            "Please send a refund email to other@test.com with body test decline case.",
            "Yes that is the right address.",
            "No, do not send the email. I changed my mind.",
        ],
    },
    {
        "id": "03_invalid_address",
        "desc": "Invalid email address",
        "turns": [
            "Send refund confirmation to not-an-email-address.",
            "Yes send anyway.",
        ],
    },
    {
        "id": "04_spelled_slow",
        "desc": "Spelled address",
        "turns": [
            "I need a refund confirmation email for a billing mistake.",
            "Double charge.",
            "The email is waseem at aidevlab dot com. Subject Refund. Body Reference GIFIC-SPELL-04.",
            "Yes, correct.",
            "Yes send.",
        ],
    },
    {
        "id": "05_free_text_body",
        "desc": "Custom body vs template policy",
        "turns": [
            "Refund confirmation email please.",
            "Overcharged.",
            f"To {TO}.",
            "Body must say exactly: TEMPLATE-BYPASS-XYZ-999 not standard template.",
            "Yes send that exact body.",
            "Yes I confirm.",
        ],
    },
    {
        "id": "06_wrong_then_correct",
        "desc": "Correct address after wrong first",
        "turns": [
            "Refund email to wrong@wrong.com please.",
            "Actually no — use waseem@aidevlab.com instead with body GIFIC-CORRECT-06.",
            "Yes send to aidevlab only.",
            "Yes confirm.",
        ],
    },
    {
        "id": "07_double_confirm",
        "desc": "Multiple yes without changing details",
        "turns": [
            f"Email refund confirmation to {TO}, body GIFIC-DOUBLE-07.",
            "Yes.",
            "Yes.",
            "Yes send.",
        ],
    },
]


def main() -> int:
    if not USER or not PW:
        print("Missing FLEXAGENTS credentials")
        return 2

    ensure_dir()
    master: dict = {
        "ticket": "GIFIC-148",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment": BASE,
        "org_id": ORG,
        "agent_id": AGENT,
        "sub_agent_id": SUB,
        "test_url": f"{BASE}/organization/{ORG}/agent/{AGENT}/test",
        "mailbox": TO,
        "log_directory": str(LOG_DIR.relative_to(ROOT)),
        "outbox_snapshot_start": fetch_outbox(),
        "console_messages": [],
        "network_samples": [],
        "setup_pages": {},
        "cases": [],
    }

    console_all: list[str] = []
    network_all: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()

        def on_console(msg):
            line = f"[{msg.type}] {msg.text}"
            console_all.append(line[:500])
            if len(console_all) <= 200:
                master["console_messages"].append(line[:500])

        def on_response(resp):
            if len(network_all) < 80 and any(x in resp.url for x in ("flexagents", "livekit", "team1", "email")):
                try:
                    network_all.append(
                        {
                            "url": resp.url[:200],
                            "status": resp.status,
                            "method": resp.request.method,
                        }
                    )
                except Exception:
                    pass

        page.on("console", on_console)
        page.on("response", on_response)

        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
        page.fill('input[type="email"]', USER)
        page.fill('input[type="password"]', PW)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(2)

        for path_key, path in (
            ("tools", f"{BASE}/organization/{ORG}/agent/{AGENT}/tools"),
            ("sub_agents", f"{BASE}/organization/{ORG}/agent/{AGENT}/sub-agents"),
            ("sub_agent_detail", f"{BASE}/organization/{ORG}/agent/{AGENT}/sub-agents/{SUB}"),
            ("activity", f"{BASE}/organization/{ORG}/agent/{AGENT}/activity"),
        ):
            try:
                page.goto(path, wait_until="networkidle", timeout=60000)
                time.sleep(1.5)
                text = page.inner_text("body")
                master["setup_pages"][path_key] = {
                    "url": path,
                    "length": len(text),
                    "has_send_email": "send_email" in text.lower(),
                    "snippet": text[:3500],
                }
                page.screenshot(path=str(LOG_DIR / f"setup_{path_key}.png"), full_page=True)
            except Exception as exc:
                master["setup_pages"][path_key] = {"error": str(exc)}

        test_url = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"

        for case in CASES:
            before = fetch_outbox()
            before_ids = {e.get("email_id") for e in before.get("results") or []}

            case_log: dict = {
                "id": case["id"],
                "description": case["desc"],
                "turns": [],
            }

            page.goto(test_url, wait_until="networkidle", timeout=90000)
            time.sleep(2)
            if page.locator("button:has-text('End Call')").count():
                try:
                    page.locator("button:has-text('End Call')").first.click(timeout=3000)
                    time.sleep(2)
                except Exception:
                    pass
            page.locator("button:has-text('Start Call')").first.click(timeout=15000)
            time.sleep(10)

            turn_idx = 0
            for utterance in case["turns"]:
                turn_idx += 1
                t0 = time.time()
                box = page.locator("input[placeholder='Type a message...']")
                box.wait_for(state="visible", timeout=60000)
                before_len = len(page.inner_text("body"))
                box.fill(utterance)
                page.keyboard.press("Enter")
                agent_reply = ""
                for _ in range(28):
                    time.sleep(2)
                    body = page.inner_text("body")
                    if len(body) > before_len + 70:
                        time.sleep(4)
                        body = page.inner_text("body")
                        # extract last agent chunk naive
                        if "Agent" in body:
                            agent_reply = body[max(0, len(body) - 1200) :]
                        break
                elapsed = round(time.time() - t0, 2)
                case_log["turns"].append(
                    {
                        "n": turn_idx,
                        "caller": utterance,
                        "elapsed_s": elapsed,
                        "agent_tail": agent_reply[-800:] if agent_reply else "",
                    }
                )

            full_body = page.inner_text("body")
            trace_i = full_body.find("Live call trace")
            transcript_i = full_body.find("Transcript")
            case_log["transcript"] = full_body[transcript_i : transcript_i + 9000] if transcript_i >= 0 else full_body[-9000:]
            case_log["live_trace"] = full_body[trace_i : trace_i + 12000] if trace_i >= 0 else ""
            case_log["trace_parse"] = parse_trace(full_body)

            page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
            log(f"case_{case['id']}.json", case_log)

            after = fetch_outbox()
            after_ids = {e.get("email_id") for e in after.get("results") or []}
            new_ids = sorted(after_ids - before_ids)
            case_log["outbox_before_count"] = before.get("count")
            case_log["outbox_after_count"] = after.get("count")
            case_log["new_team1_email_ids"] = new_ids
            case_log["new_team1_rows"] = [e for e in after.get("results") or [] if e.get("email_id") in new_ids]

            master["cases"].append(case_log)
            print(f"{case['id']}: api={case_log['trace_parse'].get('api_calls')} new_em={new_ids}")

            time.sleep(3)

        browser.close()

    master["outbox_snapshot_end"] = fetch_outbox()
    master["network_samples"] = network_all
    master["console_total_count"] = len(console_all)
    master["finished_at"] = datetime.now(timezone.utc).isoformat()

    log("MASTER.json", master)
    log("console_full.txt", "\n".join(console_all[:500]))
    log("network.json", network_all)

    # Markdown executive log
    lines = [
        "# GIFIC-148 in-depth test log",
        "",
        f"**Run:** {TS}",
        f"**Logs:** `{LOG_DIR.relative_to(ROOT)}`",
        "",
        "## Outbox (Team1)",
        f"- Start count: {master['outbox_snapshot_start'].get('count')}",
        f"- End count: {master['outbox_snapshot_end'].get('count')}",
        "",
        "## Setup",
    ]
    for k, v in master["setup_pages"].items():
        lines.append(f"- **{k}:** send_email={v.get('has_send_email')} len={v.get('length', v.get('error'))}")
    lines.extend(["", "## Cases", ""])
    for c in master["cases"]:
        tp = c["trace_parse"]
        lines.append(
            f"### {c['id']} — {c['description']}\n"
            f"- API calls (trace): {tp.get('api_calls')} | sub-agent actions: {tp.get('subagent_actions')} | "
            f"confirm: {tp.get('confirm_phrases')} | said_sent: {tp.get('said_sent')} | wont_send: {tp.get('wont_send')}\n"
            f"- Team1 new IDs: {c.get('new_team1_email_ids')}\n"
            f"- Log: `case_{c['id']}.json`, `{c['id']}.png`\n"
        )
    lines.extend(
        [
            "",
            "## How email works on this staging stack",
            "",
            "1. **Caller** → Refund Support Agent (Alex) on Test Your Agent.",
            "2. **Handoff** → Refund Email Assistant sub-agent (`subagent_refund_email_assistant` in trace when triggered).",
            "3. **Sub-agent** collects/confirm recipient + body (Ask service / confirm prompts in trace).",
            "4. **Delivery channel:** User reported real delivery as *Message from Refund Support Agent* / email to aidevlab.com; "
            "Team1 `GET /emails` may not always show a new `EM-*` for the same action.",
            "5. **Test UI** shows *Voice tests are not saved* — Activity/history may differ from Test Your Agent.",
            "",
            "## Console / network",
            f"- Console lines captured: {master['console_total_count']} (see `console_full.txt`)",
            f"- Network samples: {len(network_all)} (see `network.json`)",
        ]
    )
    md_path = ROOT / "eval/reports/GIFIC148_INDEPTH_LOG.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Log dir: {LOG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())