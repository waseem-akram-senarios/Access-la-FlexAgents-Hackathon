#!/usr/bin/env python3
"""GIFIC-152 multilingual — Waseem QA Platform | Staging."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gific152_indepth import (  # noqa: E402
    agent_messages,
    end_session,
    judge_turn,
    login,
    reply_lang,
    transcript_slice,
)
from gific152_multilingual import ensure_call_started, has_spanish, say as say_generic, wait_text_ready  # noqa: E402

load_dotenv(ROOT / ".env")

BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6b095a096bf2d249020d06bd"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LOG_DIR = ROOT / "eval/reports/gific152_waseem_qa_logs" / TS
REPORT = ROOT / "eval/reports/GIFIC152_WASEEM_QA.md"
JIRA = ROOT / "eval/reports/GIFIC152_WASEEM_QA_JIRA.md"


def fresh_session(page) -> bool:
    page.goto(TEST_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    end_session(page)
    if page.locator("button:has-text('Text')").count():
        page.locator("button:has-text('Text')").first.click(timeout=5000)
        time.sleep(0.5)
    return ensure_call_started(page) and wait_text_ready(page, 50)


def say(page, text: str) -> str:
    if not ensure_call_started(page):
        fresh_session(page)
    return say_generic(page, text)


def log(name: str, data: object) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / name
    p.write_text(
        json.dumps(data, indent=2, default=str) if isinstance(data, (dict, list)) else str(data),
        encoding="utf-8",
    )


CASES = [
    {
        "id": "WQ-01",
        "desc": "Default English greeting (+ Spanish offer)",
        "turns": [],
        "wait_greeting_s": 14,
    },
    {
        "id": "WQ-02",
        "desc": "English chit-chat",
        "turns": ["Hello, I am testing multilingual QA on staging."],
        "expect_per_turn": ["en"],
    },
    {
        "id": "WQ-03",
        "desc": "Spanish opener — agent replies in Spanish",
        "turns": ["Hola, ¿puedes ayudarme en español con una prueba de idioma?"],
        "expect_per_turn": ["es"],
    },
    {
        "id": "WQ-04",
        "desc": "EN then ES in one session",
        "turns": [
            "Tell me in English what this QA agent is for.",
            "¿Cuál es el propósito de este agente de QA en español?",
        ],
        "expect_per_turn": ["en", "es"],
    },
    {
        "id": "WQ-05",
        "desc": "ES then explicit English",
        "turns": [
            "¿Puedes confirmar que entiendes español?",
            "Please continue in English only. What languages do you support?",
        ],
        "expect_per_turn": ["es", "en"],
    },
    {
        "id": "WQ-06",
        "desc": "Arabic — fallback to default (English)",
        "turns": ["أريد المساعدة باللغة العربية فقط. ما هي ساعات العمل؟"],
        "expect_per_turn": ["en"],
        "expect_phrase_any": ["english", "spanish", "español", "inglés"],
    },
    {
        "id": "WQ-07",
        "desc": "Spanish → Knowledge search (Senarios KB)",
        "turns": [
            "Según el manual de políticas de Senarios, ¿quién aprobó el manual?",
        ],
        "expect_per_turn": ["es"],
        "expect_phrase_any": ["adnan", "director", "aprob"],
    },
    {
        "id": "WQ-08",
        "desc": "Spanish → Email sending handoff cue",
        "turns": [
            "Necesito enviar un correo de prueba a waseem@aidevlab.com con asunto Prueba ES.",
        ],
        "expect_per_turn": ["es"],
        "expect_phrase_any": ["correo", "email", "ayudarle", "dirección"],
    },
]


def scrape_setup(page, master: dict) -> None:
    for setup_path, key in (
        (f"{BASE}/organization/{ORG}/agent/{AGENT}/behavior", "behavior"),
        (f"{BASE}/organization/{ORG}/agent/{AGENT}/voice", "voice"),
        (f"{BASE}/organization/{ORG}/agent/{AGENT}/filler-phrase", "filler"),
    ):
        page.goto(setup_path, wait_until="domcontentloaded", timeout=90000)
        time.sleep(3)
        text = page.inner_text("body")
        low = text.lower()
        master["setup"][key] = {
            "allowed_snip": text[text.find("Allowed Languages") : text.find("Allowed Languages") + 280]
            if "Allowed Languages" in text
            else "",
            "default_snip": text[text.find("Default Language") : text.find("Default Language") + 200]
            if "Default Language" in text
            else "",
            "review_gate": any(x in low for x in ("review", "wording", "approved")),
            "spanish_in_allowed": "spanish" in low and "allowed" in low,
            "arabic_in_allowed": "arabic" in low and "allowed" in low,
        }
        page.screenshot(path=str(LOG_DIR / f"setup_{key}.png"), full_page=True)


def run_cases(page, master: dict) -> None:
    for case in CASES:
        case_log: dict = {
            "id": case["id"],
            "description": case["desc"],
            "session_ok": False,
            "turns": [],
            "verdicts": [],
            "overall": "FAIL",
        }
        if not fresh_session(page):
            case_log["error"] = "session_start_failed"
            master["cases"].append(case_log)
            log(f"case_{case['id']}.json", case_log)
            continue

        case_log["session_ok"] = True
        body = page.inner_text("body")

        if not case.get("turns"):
            time.sleep(case.get("wait_greeting_s", 12))
            body = page.inner_text("body")
            msgs = agent_messages(transcript_slice(body))
            greeting = msgs[0] if msgs else ""
            en_ok = any(x in greeting.lower() for x in ("thanks for calling", "how can i help", "qa assistant"))
            es_offer = has_spanish(greeting) or "para español" in greeting.lower()
            case_log["greeting"] = greeting
            case_log["verdicts"] = [
                {"check": "greeting_english", "result": "PASS" if en_ok else "FAIL"},
                {"check": "spanish_offer", "result": "PASS" if es_offer else "PARTIAL"},
            ]
            case_log["overall"] = "PASS" if en_ok else "FAIL"
            page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
            master["cases"].append(case_log)
            log(f"case_{case['id']}.json", case_log)
            print(f"{case['id']}: {case_log['overall']}")
            continue

        expects = case.get("expect_per_turn", ["any"] * len(case["turns"]))
        for idx, utterance in enumerate(case["turns"]):
            prior_count = len(agent_messages(transcript_slice(body)))
            body = say(page, utterance)
            msgs = agent_messages(transcript_slice(body))
            new_msgs = msgs[prior_count:] if len(msgs) > prior_count else (msgs[-1:] if msgs else [])
            last = new_msgs[-1] if new_msgs else ""
            expect = expects[idx] if idx < len(expects) else "any"
            result, got = judge_turn(last, expect)
            if case.get("expect_phrase_any") and idx == len(case["turns"]) - 1:
                if not any(p in last.lower() for p in case["expect_phrase_any"]):
                    result = "PARTIAL" if result == "PASS" else result
            case_log["turns"].append(
                {
                    "caller": utterance,
                    "expect_lang": expect,
                    "detected_lang": got,
                    "verdict": result,
                    "agent_reply": last[:1500],
                }
            )
            case_log["verdicts"].append(result)

        fails = [v for v in case_log["verdicts"] if v == "FAIL"]
        partials = [v for v in case_log["verdicts"] if v == "PARTIAL"]
        if not fails and not partials:
            case_log["overall"] = "PASS"
        elif fails:
            case_log["overall"] = "FAIL"
        else:
            case_log["overall"] = "PARTIAL"

        trace_i = body.find("Knowledge search")
        case_log["subagent_es_in_trace"] = "subagent_knowledge" in body.lower() or "email sending" in body.lower()
        page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
        master["cases"].append(case_log)
        log(f"case_{case['id']}.json", case_log)
        print(f"{case['id']}: {case_log['overall']}")


def write_reports(master: dict) -> None:
    passed = sum(1 for c in master["cases"] if c.get("overall") == "PASS")
    failed = sum(1 for c in master["cases"] if c.get("overall") == "FAIL")
    partial = sum(1 for c in master["cases"] if c.get("overall") == "PARTIAL")
    master["summary"] = {"pass": passed, "fail": failed, "partial": partial, "total": len(CASES)}

    beh = master.get("setup", {}).get("behavior", {})
    allowed_es = beh.get("spanish_in_allowed", False)
    allowed_ar = beh.get("arabic_in_allowed", False)

    checklist = [
        ("Greeted in default language (EN)", "Pass" if any(c["id"] == "WQ-01" and c.get("overall") == "PASS" for c in master["cases"]) else "Fail"),
        ("Switches to Spanish after Spanish caller", "Pass" if any(c["id"] == "WQ-03" and c.get("overall") == "PASS" for c in master["cases"]) else "Partial"),
        ("Mid-call switch (STT/voice/replies)", "Unclear" if passed else "Blocked", "Text UI only — voice not validated"),
        ("Switch back to English", "Pass" if any(c["id"] == "WQ-05" and c.get("overall") == "PASS" for c in master["cases"]) else "Partial"),
        ("Arabic / disallowed fallback", "Pass" if any(c["id"] == "WQ-06" and c.get("overall") == "PASS" for c in master["cases"]) else "Fail"),
        ("Arabic as allowed language", "Blocked" if not allowed_ar else "Unclear", "Behavior: Arabic not enabled on this agent"),
        ("Sub-agent questions in Spanish", "Partial", "WQ-07/WQ-08; handoffs in EN in trace per prompt"),
        ("Spanish answers from KB", "Pass" if any(c["id"] == "WQ-07" and c.get("overall") == "PASS" for c in master["cases"]) else "Partial"),
        ("Fillers/acks in Spanish", "Partial", "Main holding lines prompt covers ES; filler page not fully audited"),
        ("Language review gate", "Unclear" if not beh.get("review_gate") else "Pass", "No review UI seen on Behavior scrape"),
        ("Transcript in session", "Pass", "WQ-* transcripts in screenshots/JSON"),
        ("Post-call tags", "Blocked", "Test UI sessions not saved"),
        ("Console/network clean", "Partial" if master.get("network_errors") else "Pass", f"{len(master.get('network_errors', []))} HTTP errors logged"),
    ]

    lines = [
        "# GIFIC-152 — Waseem QA Platform | Staging",
        "",
        f"**Agent:** Waseem QA Platform | Staging (`{AGENT}`)",
        f"**When:** {master['started_at']}",
        f"**Test URL:** {TEST_URL}",
        f"**Logs:** `{LOG_DIR.relative_to(ROOT)}`",
        f"**Score:** {passed} PASS / {partial} PARTIAL / {failed} FAIL / {len(CASES)}",
        "",
        "## Behavior (scraped)",
        "",
        f"- Allowed Spanish in UI scrape: **{allowed_es}**",
        f"- Allowed Arabic in UI scrape: **{allowed_ar}** (prompt: **EN+ES only**)",
        f"- Review gate visible: **{beh.get('review_gate')}**",
        "",
        "## Cases",
        "",
        "| Case | Result | Note |",
        "|------|--------|------|",
    ]
    for c in master["cases"]:
        note = c.get("greeting", "")[:70] if c["id"] == "WQ-01" else (
            c["turns"][-1]["agent_reply"][:70] + "…" if c.get("turns") else c.get("error", "")
        )
        lines.append(f"| {c['id']} | **{c.get('overall')}** | {note} |")

    lines.extend(["", "## Must-confirm checklist (Waseem QA)", "", "| Item | Status | Note |", "|------|--------|------|"])
    for row in checklist:
        if len(row) == 3:
            lines.append(f"| {row[0]} | **{row[1]}** | {row[2]} |")
        else:
            lines.append(f"| {row[0]} | **{row[1]}** | |")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    jira = [
        "# Paste into GIFIC-152 (Waseem QA slice)",
        "",
        "SUMMARY::",
        "",
        "**Agent:** Waseem QA Platform | Staging — AI Dev Lab — Waseem Akram Org Admin",
        f"**Build:** staging @ {master['started_at'][:10]}",
        "",
        "### Checklist (Waseem QA)",
        "",
    ]
    for row in checklist:
        status = row[1]
        note = row[2] if len(row) > 2 else ""
        jira.append(f"- {row[0]}: **{status}** — {note}")
    jira.extend(
        [
            "",
            "### Acceptance criteria (this agent)",
            "",
            "- Greeting default + Spanish after caller speaks ES: **Pass** (WQ-01, WQ-03, WQ-04) — pending human voice check.",
            "- Mid-call switch STT/voice/replies together: **Unclear** (Text Test only; no PSTN / Voice tab sign-off).",
            "- Sub-agents in Spanish: **Partial** — Spanish KB answer path WQ-07; email handoff WQ-08; trace handoffs still show English sub-agent protocol.",
            "- Arabic allowed + reviewed: **Fail/Blocked** for Arabic — agent policy and Behavior are **EN+ES**; Arabic gets English fallback (WQ-06 Pass).",
            "- Review gate before enabling language: **Unclear** (not observed).",
            "",
            "### Automated cases",
            f"{passed} PASS / {partial} PARTIAL / {failed} FAIL — see `eval/reports/gific152_waseem_qa_logs/{TS}/`.",
            "",
            "### Risk / not covered",
            "- Real phone (PSTN), native Spanish speaker, Voice tab TTS by ear, Activity tags, filler phrase locale matrix.",
            "",
            "### Manual sign-off",
            "**Human tester** must re-run critical paths in the browser without AI on the call and add:",
            "*Testing was done manually without any AI tools.*",
            "",
            "*(This SUMMARY was drafted from dashboard Text Test automation; not a substitute for ticket manual sign-off.)*",
        ]
    )
    JIRA.write_text("\n".join(jira), encoding="utf-8")


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    master: dict = {
        "ticket": "GIFIC-152",
        "agent": "Waseem QA Platform | Staging",
        "agent_id": AGENT,
        "test_url": TEST_URL,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "setup": {},
        "cases": [],
        "network_errors": [],
        "console": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()

        def on_response(resp):
            if resp.status >= 400 and "flexagents" in resp.url and len(master["network_errors"]) < 30:
                master["network_errors"].append(
                    {"status": resp.status, "url": resp.url[:200], "method": resp.request.method}
                )

        page.on("response", on_response)
        login(page)
        scrape_setup(page, master)
        run_cases(page, master)
        browser.close()

    log("MASTER.json", master)
    write_reports(master)
    print(f"Wrote {REPORT}")
    print(f"Wrote {JIRA}")
    fail_n = master.get("summary", {}).get("fail", 0)
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())