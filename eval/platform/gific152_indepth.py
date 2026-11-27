#!/usr/bin/env python3
"""GIFIC-152 in-depth multilingual testing — Access LA Jenny (staging test UI)."""

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
from gific152_multilingual import (  # noqa: E402
    analyze,
    ensure_call_started,
    has_arabic,
    has_spanish,
    login,
    say,
    text_input_ready,
    wait_text_ready,
)

load_dotenv(ROOT / ".env")
import os  # noqa: E402

USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENT = "6af703a01d07b8f78656fe4f"
TEST_URL = f"{BASE}/organization/{ORG}/agent/{AGENT}/test"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LOG_DIR = ROOT / "eval/reports/gific152_indepth_logs" / TS


def log(name: str, data: object) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / name
    if isinstance(data, (dict, list)):
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        p.write_text(str(data), encoding="utf-8")


def end_session(page) -> None:
    for label in ("End Session", "End Call"):
        loc = page.locator(f"button:has-text('{label}')")
        if loc.count() and loc.first.is_visible():
            try:
                loc.first.click(timeout=5000)
                time.sleep(2)
            except Exception:
                pass
            return


def fresh_session(page) -> bool:
    page.goto(TEST_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    end_session(page)
    if page.locator("button:has-text('Text')").count():
        page.locator("button:has-text('Text')").first.click(timeout=5000)
        time.sleep(0.5)
    return ensure_call_started(page) and wait_text_ready(page, 50)


def transcript_slice(body: str) -> str:
    i = body.find("Transcript")
    return body[i : i + 20000] if i >= 0 else body[-12000:]


def agent_messages(transcript: str) -> list[str]:
    block = transcript_slice(transcript) if "Transcript" not in transcript[:20] else transcript
    msgs: list[str] = []
    for m in re.finditer(
        r"Agent\n\d{1,2}:\d{2}:\d{2}\s[AP]M\n\n(.+?)(?=\n\n(?:Y\nYou|A\nAgent|Scroll to end)|\Z)",
        block,
        re.DOTALL,
    ):
        t = re.sub(r"\s+", " ", m.group(1).strip())
        if t:
            msgs.append(t)
    return msgs


def reply_lang(text: str) -> str:
    if has_arabic(text):
        return "ar"
    es_hits = len(
        re.findall(
            r"\b(solo|puedo|ayudarle|déjeme|dejeme|verificarlo|horarios|tarifa|usted|español|gracias|quién|llamo|disculpe|información)\b",
            text.lower(),
        )
    )
    en_hits = len(
        re.findall(
            r"\b(the|you|can|help|access|services|sorry|thanks|calling|only|general|inquiry)\b",
            text.lower(),
        )
    )
    if es_hits >= 2 and es_hits >= en_hits:
        return "es"
    if es_hits >= 1 and en_hits == 0:
        return "es"
    return "en"


def judge_turn(last_agent: str, expect: str) -> tuple[str, str]:
    """expect: en | es | en_or_es | any"""
    got = reply_lang(last_agent)
    if expect == "any":
        return "PASS", got
    if expect == "en_or_es":
        return ("PASS", got) if got in ("en", "es") else ("FAIL", got)
    if got == expect:
        return "PASS", got
    if expect == "en" and "para español" in last_agent.lower() and got == "en":
        return "PASS", got
    return "FAIL", got


CASES = [
    {
        "id": "ML-01",
        "desc": "Unprompted greeting language (default EN)",
        "turns": [],
        "wait_greeting_s": 12,
        "expect_greeting_en": True,
    },
    {
        "id": "ML-02",
        "desc": "English fare question — reply in English",
        "turns": ["What's the current one-way Access fare?"],
        "expect_per_turn": ["en"],
    },
    {
        "id": "ML-03",
        "desc": "Spanish-only fare question — reply in Spanish",
        "turns": ["¿Cuál es la tarifa actual de ida de Access?"],
        "expect_per_turn": ["es"],
    },
    {
        "id": "ML-04",
        "desc": "EN then ES switch in one session",
        "turns": [
            "What are your hours today?",
            "¿Cuáles son los horarios de hoy?",
        ],
        "expect_per_turn": ["en", "es"],
    },
    {
        "id": "ML-05",
        "desc": "ES then explicit request for English",
        "turns": [
            "¿Cuál es la tarifa de ida?",
            "Please answer in English. What is the one-way fare?",
        ],
        "expect_per_turn": ["es", "en"],
    },
    {
        "id": "ML-06",
        "desc": "Spanish lost-item (sub-agent / find_department)",
        "turns": ["Dejé mi mochila en el autobús número 7. ¿A quién llamo?"],
        "expect_per_turn": ["es"],
        "expect_phrase_any": ["déjeme", "dejeme", "verificarlo", "lost"],
    },
    {
        "id": "ML-07",
        "desc": "Arabic request — fallback to default (English)",
        "turns": ["أريد معرفة رسوم الرحلة. أتحدث العربية فقط."],
        "expect_per_turn": ["en"],
    },
    {
        "id": "ML-08",
        "desc": "Mixed EN+ES in one utterance",
        "turns": ["I need the tarifa for Access one-way trip please."],
        "expect_per_turn": ["en_or_es"],
    },
    {
        "id": "ML-09",
        "desc": "Spanish with phone number and time",
        "turns": [
            "Perdí mi tarjeta ayer. Mi teléfono es 213-555-0199. ¿Pueden devolverme una llamada mañana a las 2 de la tarde?"
        ],
        "expect_per_turn": ["es"],
    },
    {
        "id": "ML-10",
        "desc": "Switch back: ES → EN mid session",
        "turns": [
            "Hola, ¿está abierto Lost and Found ahora?",
            "Thanks. Please continue in English only. Is Lost and Found open now?",
        ],
        "expect_per_turn": ["es", "en"],
    },
]


def main() -> int:
    master: dict = {
        "ticket": "GIFIC-152",
        "agent": "Access LA Jenny",
        "agent_id": AGENT,
        "test_url": TEST_URL,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "log_dir": str(LOG_DIR.relative_to(ROOT)),
        "console": [],
        "network_errors": [],
        "setup": {},
        "cases": [],
        "summary": {},
    }

    console: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()

        def on_console(msg):
            line = f"[{msg.type}] {msg.text}"[:500]
            if len(console) < 150:
                console.append(line)

        def on_response(resp):
            if resp.status >= 400 and "flexagents" in resp.url:
                if len(master["network_errors"]) < 40:
                    master["network_errors"].append(
                        {"status": resp.status, "url": resp.url[:220], "method": resp.request.method}
                    )

        page.on("console", on_console)
        page.on("response", on_response)

        login(page)
        for setup_path, key in (
            (f"{BASE}/organization/{ORG}/agent/{AGENT}/behavior", "behavior"),
            (f"{BASE}/organization/{ORG}/agent/{AGENT}/voice", "voice"),
            (f"{BASE}/organization/{ORG}/agent/{AGENT}/filler-phrase", "filler"),
        ):
            page.goto(setup_path, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2.5)
            text = page.inner_text("body")
            master["setup"][key] = {
                "allowed": text[text.find("Allowed Languages") : text.find("Allowed Languages") + 200]
                if "Allowed Languages" in text
                else "",
                "default": text[text.find("Default Language") : text.find("Default Language") + 200]
                if "Default Language" in text
                else "",
                "snippet_len": len(text),
            }
            page.screenshot(path=str(LOG_DIR / f"setup_{key}.png"), full_page=True)

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
                time.sleep(case.get("wait_greeting_s", 10))
                body = page.inner_text("body")
                msgs = agent_messages(transcript_slice(body))
                greeting = msgs[0] if msgs else ""
                en_ok = "thanks for calling" in greeting.lower() or "how can i help" in greeting.lower()
                case_log["greeting"] = greeting
                case_log["verdicts"].append(
                    {
                        "check": "greeting_english",
                        "result": "PASS" if en_ok else "FAIL",
                        "greeting_lang": reply_lang(greeting),
                    }
                )
                case_log["overall"] = "PASS" if en_ok else "FAIL"
                page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
                master["cases"].append(case_log)
                log(f"case_{case['id']}.json", case_log)
                continue

            expects = case.get("expect_per_turn", ["any"] * len(case["turns"]))
            for idx, utterance in enumerate(case["turns"]):
                t0 = time.time()
                prior_count = len(agent_messages(transcript_slice(body)))
                try:
                    body = say(page, utterance)
                except Exception as exc:
                    case_log["turns"].append({"caller": utterance, "error": str(exc)})
                    break
                msgs = agent_messages(transcript_slice(body))
                new_msgs = msgs[prior_count:] if len(msgs) > prior_count else (msgs[-1:] if msgs else [])
                last = new_msgs[-1] if new_msgs else ""
                expect = expects[idx] if idx < len(expects) else "any"
                result, got = judge_turn(last, expect)
                phrase_ok = True
                if case.get("expect_phrase_any") and idx == len(case["turns"]) - 1:
                    phrase_ok = any(p in last.lower() for p in case["expect_phrase_any"])
                    if not phrase_ok:
                        result = "PARTIAL" if result == "PASS" else result

                turn_rec = {
                    "n": idx + 1,
                    "caller": utterance,
                    "elapsed_s": round(time.time() - t0, 2),
                    "expect_lang": expect,
                    "detected_lang": got,
                    "verdict": result if phrase_ok else "PARTIAL",
                    "agent_reply": last[:1200],
                    "signals": analyze(body, True),
                }
                case_log["turns"].append(turn_rec)
                case_log["verdicts"].append(result if phrase_ok else "PARTIAL")

            fails = [v for v in case_log["verdicts"] if v in ("FAIL",)]
            partials = [v for v in case_log["verdicts"] if v == "PARTIAL"]
            if not fails and not partials:
                case_log["overall"] = "PASS"
            elif fails:
                case_log["overall"] = "FAIL"
            else:
                case_log["overall"] = "PARTIAL"

            case_log["transcript"] = transcript_slice(body)[:14000]
            i = body.find("Live call trace")
            case_log["live_trace_snip"] = body[i : i + 8000] if i >= 0 else ""
            page.screenshot(path=str(LOG_DIR / f"{case['id']}.png"), full_page=True)
            master["cases"].append(case_log)
            log(f"case_{case['id']}.json", case_log)
            print(f"{case['id']}: {case_log['overall']}")

        master["console"] = console
        browser.close()

    passed = sum(1 for c in master["cases"] if c.get("overall") == "PASS")
    failed = sum(1 for c in master["cases"] if c.get("overall") == "FAIL")
    partial = sum(1 for c in master["cases"] if c.get("overall") == "PARTIAL")
    master["summary"] = {"pass": passed, "fail": failed, "partial": partial, "total": len(CASES)}

    log("MASTER.json", master)
    md = LOG_DIR.parent.parent / "GIFIC152_INDEPTH.md"
    lines = [
        f"# GIFIC-152 in-depth — Jenny multilingual (`{TS}`)",
        "",
        f"**URL:** {TEST_URL}",
        "",
        f"**Score:** {passed} PASS / {partial} PARTIAL / {failed} FAIL / {len(CASES)} cases",
        "",
        "| Case | Result | Notes |",
        "| --- | --- | --- |",
    ]
    for c in master["cases"]:
        note = c.get("error") or (c["turns"][-1]["agent_reply"][:80] + "…" if c.get("turns") else c.get("greeting", "")[:80])
        lines.append(f"| {c['id']} | {c.get('overall')} | {note} |")
    lines.extend(["", f"Logs: `{LOG_DIR.relative_to(ROOT)}`"])
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {LOG_DIR}/MASTER.json and {md}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())