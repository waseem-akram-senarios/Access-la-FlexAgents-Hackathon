#!/usr/bin/env python3
"""Test Waseem QA Platform sub-agents: Knowledge search + Email sending (staging Text UI)."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
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
LOG_DIR = ROOT / "eval/reports/waseem_qa_subagents_logs" / TS
REPORT_MD = ROOT / "eval/reports/WASEEM_QA_SUBAGENTS_TEST.md"


def fresh_session(page) -> bool:
    page.goto(TEST_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    if page.locator("button:has-text('Text')").count():
        page.locator("button:has-text('Text')").first.click()
        time.sleep(0.5)
    for label in ("End Session", "End Call"):
        loc = page.locator(f"button:has-text('{label}')")
        if loc.count():
            try:
                loc.first.click(timeout=3000)
                time.sleep(2)
            except Exception:
                pass
    return ensure_call_started(page) and wait_text_ready(page, 50)


def trace_metrics(body: str) -> dict:
    low = body.lower()
    m_api = re.search(r"api calls\s*(\d+)", low)
    m_sub = re.search(r"agent and sub-agents\s*(\d+)", low)
    return {
        "api_calls": int(m_api.group(1)) if m_api else None,
        "subagent_actions": int(m_sub.group(1)) if m_sub else None,
        "handoff_kb": any(
            x in low for x in ("look that up", "materials", "knowledge search", "search_knowledge")
        ),
        "handoff_email": any(
            x in low for x in ("help you with that email", "email sending", "email now")
        ),
        "kb_answer": any(x in low for x in ("hour", "document", "material", "service", "fare", "found")),
        "kb_not_found": any(x in low for x in ("not found", "no encontr", "could not find", "materials")),
        "confirm_email": bool(re.search(r"confirm|is that (right|correct)", low)),
        "readback_email": TO.split("@")[0] in low or "aidevlab" in low,
        "said_sent": bool(re.search(r"sent|accepted for delivery|email has been", low)),
        "cannot_email": any(x in low for x in ("can't send", "cannot send", "no tool", "not connected")),
        "invalid_handled": any(x in low for x in ("not valid", "invalid", "isn't a valid")),
        "trace_snip": body[body.find("Agent and sub-agents") : body.find("Agent and sub-agents") + 800]
        if "Agent and sub-agents" in body
        else "",
    }


def fetch_outbox_before_after() -> tuple[set[str], set[str]]:
    try:
        url = f"https://team1-inquiry-api.vercel.app/emails?to={TO}&limit=15"
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
        ids = {e.get("email_id") for e in data.get("results") or [] if e.get("email_id")}
        return ids, ids
    except Exception:
        return set(), set()


CASES = [
    {
        "id": "K01_kb_hours",
        "sub": "Knowledge search",
        "desc": "Policy / hours style KB question",
        "turns": [
            "What are the Access LA weekday Customer Service hours? I need the answer from your materials.",
        ],
        "pass_if": lambda m: m["handoff_kb"] or m["kb_answer"] or (m.get("subagent_actions") or 0) > 0,
    },
    {
        "id": "K02_kb_nonsense",
        "sub": "Knowledge search",
        "desc": "Unlikely topic — should not invent",
        "turns": [
            "What is the fare to Mars on the purple unicorn route for Access LA?",
        ],
        "pass_if": lambda m: m["kb_not_found"] or "could not" in (m.get("trace_snip") or "").lower() or m["handoff_kb"],
    },
    {
        "id": "E01_email_happy",
        "sub": "Email sending",
        "desc": "Handoff + confirm + send",
        "turns": [
            "I need a test confirmation email sent for GIFIC-148 QA on Waseem QA Platform.",
            f"Send to {TO}. Subject: QA Sub-agent Test. Body: WASEEM-SUB-E01.",
            "Yes, that address is correct.",
            "Yes, send it now.",
        ],
        "pass_if": lambda m: (m["handoff_email"] or m["confirm_email"]) and not m["cannot_email"],
    },
    {
        "id": "E02_email_decline",
        "sub": "Email sending",
        "desc": "Decline before send",
        "turns": [
            f"Please email me at {TO} with body DECLINE-SUB-02.",
            "Yes the address is right.",
            "No, do not send the email.",
        ],
        "pass_if": lambda m: m["handoff_email"] or m["confirm_email"],
    },
]


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    master: dict = {
        "agent": "Waseem QA Platform | Staging",
        "agent_id": AGENT,
        "test_url": TEST_URL,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cases": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)
        for path, key in (
            ("sub-agents", "sub_agents"),
            ("tools", "tools"),
            ("knowledge", "knowledge"),
        ):
            try:
                page.goto(f"{BASE}/organization/{ORG}/agent/{AGENT}/{path}", wait_until="domcontentloaded")
                time.sleep(4)
                t = page.inner_text("body")
                master[f"setup_{key}"] = {
                    "email_sub": "Email sending" in t,
                    "kb_sub": "Knowledge search" in t,
                    "kb_attached": "Knowledge base" in t and "No knowledge" not in t[:1200],
                    "snippet": t[:1500],
                }
                page.screenshot(path=str(LOG_DIR / f"setup_{path}.png"), full_page=True)
            except Exception as exc:
                master[f"setup_{path}"] = {"error": str(exc)}

        outbox_before, _ = fetch_outbox_before_after()

        for case in CASES:
            row = {
                "id": case["id"],
                "sub_agent": case["sub"],
                "description": case["desc"],
                "session_ok": False,
                "turns": [],
            }
            if not fresh_session(page):
                row["error"] = "session_failed"
                row["verdict"] = "Blocked"
                master["cases"].append(row)
                continue
            row["session_ok"] = True
            body = ""
            for utterance in case["turns"]:
                t0 = time.time()
                body = say(page, utterance)
                tail = body[max(0, body.rfind("Agent")) :][:700]
                row["turns"].append(
                    {"caller": utterance, "elapsed_s": round(time.time() - t0, 2), "agent_tail": tail}
                )
            row["metrics"] = trace_metrics(body)
            row["verdict"] = "Pass" if case["pass_if"](row["metrics"]) else "Fail"
            if case["id"] == "E01_email_happy":
                row["metrics"]["said_sent_strict"] = row["metrics"]["said_sent"]
                if (row["metrics"].get("api_calls") or 0) < 1 and not row["metrics"]["said_sent"]:
                    row["verdict"] = "Partial"
            page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
            master["cases"].append(row)
            print(case["id"], row["verdict"], row["metrics"])

        _, outbox_after_ids = fetch_outbox_before_after()
        master["team1_new_email_ids"] = list(outbox_after_ids - outbox_before)
        browser.close()

    (LOG_DIR / "MASTER.json").write_text(json.dumps(master, indent=2), encoding="utf-8")

    lines = [
        "# Waseem QA Platform — sub-agent test run",
        "",
        f"- **When:** {master['started_at']}",
        f"- **Logs:** `{LOG_DIR.relative_to(ROOT)}`",
        f"- **Test URL:** {TEST_URL}",
        "",
        "## Setup (dashboard scrape)",
        "",
    ]
    for key in ("sub_agents", "tools", "knowledge"):
        s = master.get(f"setup_{key}")
        if isinstance(s, dict):
            lines.append(f"- **{key}:** email sub={s.get('email_sub')} | kb sub={s.get('kb_sub')} | KB attached={s.get('kb_attached')}")
    lines.extend(["", "## Cases", "", "| ID | Sub-agent | Verdict | API calls | Sub-agent actions | Notes |", "|---|---|---|---:|---:|---|"])
    for c in master["cases"]:
        m = c.get("metrics") or {}
        notes = []
        if m.get("cannot_email"):
            notes.append("no send tool")
        if m.get("said_sent"):
            notes.append("said sent/accepted")
        if m.get("handoff_kb"):
            notes.append("KB handoff cue")
        if m.get("handoff_email"):
            notes.append("email handoff cue")
        lines.append(
            f"| {c['id']} | {c.get('sub_agent','')} | **{c.get('verdict','?')}** | "
            f"{m.get('api_calls','—')} | {m.get('subagent_actions','—')} | {', '.join(notes) or c.get('error','')} |"
        )
    lines.extend(
        [
            "",
            f"- **Team1 new email IDs:** {master.get('team1_new_email_ids') or 'none'}",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {LOG_DIR / 'MASTER.json'}")
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())