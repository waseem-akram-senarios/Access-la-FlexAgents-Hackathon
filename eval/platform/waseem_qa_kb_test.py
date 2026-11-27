#!/usr/bin/env python3
"""Knowledge search sub-agent — Waseem QA Platform (staging)."""

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
from gific152_multilingual import ensure_call_started, login, text_input_ready, wait_text_ready  # noqa: E402

load_dotenv(ROOT / ".env")
import os  # noqa: E402

USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b095a096bf2d249020d06bd"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
KB_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/knowledge-base"
DOC = "Policy Manual_Senarios (PDF in agent Knowledge base)"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LOG_DIR = ROOT / "eval/reports/waseem_qa_kb_logs" / TS


def fresh_session(page) -> bool:
    page.goto(TEST_URL, wait_until="networkidle", timeout=90000)
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
    return ensure_call_started(page) and wait_text_ready(page, 60)


def say_long(page, text: str, wait_s: float = 90.0) -> str:
    if not wait_text_ready(page, 30):
        return page.inner_text("body")
    box = page.locator(
        "input[placeholder='Type a message...'], input[placeholder*='send a message' i], textarea[placeholder*='message' i]"
    )
    marker = page.inner_text("body").count("Agent\n")
    box.fill(text)
    page.keyboard.press("Enter")
    t0 = time.time()
    last = ""
    while time.time() - t0 < wait_s:
        time.sleep(3)
        body = page.inner_text("body")
        last = body
        if body.count("Agent\n") > marker + 0:
            # wait for sub-agent / trace to settle
            if "Knowledge search" in body or "search_knowledge" in body.lower():
                time.sleep(8)
                last = page.inner_text("body")
                break
            if re.search(r"Agent\n\d{1,2}:\d{2}:\d{2}", body[body.rfind("Transcript") :]):
                time.sleep(6)
                last = page.inner_text("body")
                if "listening" in body.lower() and time.time() - t0 > 20:
                    break
        if (m := re.search(r"agent and sub-agents\s*(\d+)", body.lower())) and int(m.group(1)) > 0:
            time.sleep(10)
            last = page.inner_text("body")
            break
    return last


def agent_replies(body: str) -> list[str]:
    tx = body[body.find("Transcript") :] if "Transcript" in body else body
    msgs = []
    for m in re.finditer(
        r"Agent\n\d{1,2}:\d{2}:\d{2}\s[AP]M\n\n(.+?)(?=\n\n(?:Y\nYou|A\nAgent)|\Z)",
        tx,
        re.DOTALL,
    ):
        t = re.sub(r"\s+", " ", m.group(1).strip())
        if t and "Thanks for calling the Waseem QA" not in t:
            msgs.append(t)
    return msgs


def analyze(body: str) -> dict:
    low = body.lower()
    m_api = re.search(r"api calls\s*(\d+)", low)
    m_sub = re.search(r"agent and sub-agents\s*(\d+)", low)
    replies = agent_replies(body)
    return {
        "api_calls": int(m_api.group(1)) if m_api else None,
        "subagent_actions": int(m_sub.group(1)) if m_sub else None,
        "handoff_kb_subagent": "knowledge search" in low
        or "subagent_knowledge" in low.replace(" ", "_")
        or "hand off: subagent_knowledge" in low,
        "search_knowledge_in_trace": "search_knowledge" in low or "knowledge base" in low,
        "kb_spoken_answer": bool(replies),
        "agent_replies": replies[-3:],
        "not_found": any(x in low for x in ("not found", "could not find", "no encontr", "not in the materials")),
        "partial_trace": "partial" in low and "waiting for captured" in low,
        "trace_has_kb": "knowledge search" in body[body.find("Detailed") :] if "Detailed" in body else False,
    }


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out: dict = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kb_document": DOC,
        "kb_page": {},
        "cases": [],
    }

    # Ground truth from Policy Manual_Senarios PDF (local copy for grading).
    queries = [
        (
            "S01_title",
            "From the Policy Manual in your knowledge base, what is the manual about?",
            ["senarios", "employment", "workplace", "policy manual"],
        ),
        (
            "S02_approval",
            "According to the Senarios policy manual, who approved the policy manual?",
            ["adnan", "managing director"],
        ),
        (
            "S03_lunch",
            "What are the lunch break hours in the Senarios attendance policy?",
            ["2:00", "3:00", "2:00 pm", "3:00 pm"],
        ),
        (
            "S04_off_topic",
            "What is the fare to Mars on the purple unicorn route?",
            [],
        ),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_context(viewport={"width": 1500, "height": 1600}).new_page()
        login(page)

        page.goto(KB_URL, wait_until="networkidle", timeout=90000)
        time.sleep(4)
        kb_body = page.inner_text("body")
        out["kb_page"] = {
            "url": KB_URL,
            "has_documents": any(
                x in kb_body.lower()
                for x in ("document", "upload", "indexed", "pdf", ".md", "file")
            )
            and "no documents" not in kb_body.lower(),
            "snippet": kb_body[kb_body.find("Knowledge") : kb_body.find("Knowledge") + 2500]
            if "Knowledge" in kb_body
            else kb_body[:2000],
        }
        page.screenshot(path=str(LOG_DIR / "knowledge_page.png"), full_page=True)

        for item in queries:
            cid, question = item[0], item[1]
            expect_any = item[2] if len(item) > 2 else []
            row = {"id": cid, "question": question, "session_ok": False}
            if not fresh_session(page):
                row["error"] = "session_failed"
                out["cases"].append(row)
                continue
            row["session_ok"] = True
            body = say_long(page, question, wait_s=100)
            row["analysis"] = analyze(body)
            blob = " ".join(row["analysis"].get("agent_replies") or []).lower() + " " + body.lower()
            if cid == "S04_off_topic":
                row["content_match"] = row["analysis"]["not_found"] or any(
                    x in blob for x in ("not available", "could not find", "do not know", "no information")
                )
                row["verdict"] = "Pass" if row["content_match"] else "Fail"
            elif expect_any:
                row["content_match"] = any(e in blob for e in expect_any)
                row["verdict"] = "Pass" if row["content_match"] and row["analysis"]["handoff_kb_subagent"] else (
                    "Partial" if row["analysis"]["handoff_kb_subagent"] else "Fail"
                )
            else:
                row["verdict"] = "Pass" if row["analysis"]["handoff_kb_subagent"] else "Fail"
            if row["analysis"]["partial_trace"] and row["verdict"] != "Pass":
                row["verdict"] = "Partial"
            page.screenshot(path=str(LOG_DIR / f"{cid}.png"), full_page=True)
            out["cases"].append(row)
            print(cid, row["verdict"], row.get("content_match"), row["analysis"].get("agent_replies"))

        browser.close()

    (LOG_DIR / "MASTER.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote", LOG_DIR / "MASTER.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())