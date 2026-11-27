#!/usr/bin/env python3
"""GIFIC-152 multilingual exploratory (Jenny + Refund agents)."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
import os  # noqa: E402

USER, PW = os.getenv("FLEXAGENTS_USERNAME"), os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AGENTS = {
    "jenny": ("6af703a01d07b8f78656fe4f", "Access LA Jenny"),
    "refund": ("6b0066ba91c89920b65d5dae", "Refund Support Agent"),
}
OUT = ROOT / "eval/reports/gific152_multilingual.json"


def has_spanish(text: str) -> bool:
    low = text.lower()
    return bool(
        re.search(
            r"español|para español|déjeme|verificarlo|gracias|puedo ayudarle|horario|tarifa|¿",
            low,
            re.I,
        )
    )


def has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


def analyze(tx: str, default_en_greeting: bool) -> dict:
    low = tx.lower()
    return {
        "english_greeting": "thanks for calling" in low or "how may" in low or "how can i help" in low,
        "spanish_reply": has_spanish(tx),
        "arabic_reply": has_arabic(tx),
        "spanish_greeting_offer": "para español" in low or "hable en español" in low,
        "unprompted_spanish": has_spanish(tx) and default_en_greeting and "para español" not in low[:500],
        "stt_mentioned": "assemblyai" in low,
    }


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=90000)
    page.fill('input[type="email"]', USER or "")
    page.fill('input[type="password"]', PW or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded", timeout=90000)
    time.sleep(2)


def text_input_ready(page) -> bool:
    box = page.locator(
        "input[placeholder='Type a message...'], input[placeholder*='send a message' i], textarea[placeholder*='message' i]"
    )
    return box.count() > 0 and box.first.is_enabled()


def session_active(page) -> bool:
    body = page.inner_text("body").lower()
    if "connecting..." in body:
        return False
    if text_input_ready(page):
        return True
    return "live session active" in body and "speak to begin" not in body


def ensure_call_started(page) -> bool:
    if session_active(page):
        return True
    if page.locator("button:has-text('Text')").count():
        page.locator("button:has-text('Text')").first.click(timeout=5000)
        time.sleep(0.5)
    for _ in range(3):
        for label in ("Start Session", "Start Call"):
            start = page.locator(f"button:has-text('{label}')")
            if start.count() and start.first.is_visible():
                start.first.click(timeout=15000)
                for __ in range(15):
                    time.sleep(2)
                    if session_active(page):
                        return True
                    if "thanks for calling" in page.inner_text("body").lower():
                        return True
        time.sleep(2)
    return session_active(page)


def wait_text_ready(page, timeout_s: float = 45.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if text_input_ready(page):
            return True
        time.sleep(2)
    return text_input_ready(page)


def say(page, text: str) -> str:
    if not ensure_call_started(page):
        return page.inner_text("body")
    if not wait_text_ready(page):
        raise RuntimeError("test chat input disabled; live session did not finish connecting")
    box = page.locator(
        "input[placeholder='Type a message...'], input[placeholder*='send a message' i], textarea[placeholder*='message' i]"
    )
    box.wait_for(state="visible", timeout=60000)
    marker = page.inner_text("body").count("Agent\n")
    box.fill(text)
    page.keyboard.press("Enter")
    for _ in range(36):
        time.sleep(2)
        body = page.inner_text("body")
        if body.count("Agent\n") > marker:
            time.sleep(5)
            break
    return page.inner_text("body")


CASES = {
    "jenny": [
        (
            "en_es_flow",
            [
                "What's the one-way Access fare?",
                "¿Cuál es la tarifa de ida de Access?",
                "Please answer in English. What is the fare?",
                "Dejé mi bolso en el autobús. ¿A quién llamo?",
                "ما هي رسوم الرحلة؟ أريد المساعدة بالعربية.",
            ],
        ),
    ],
    "refund": [
        (
            "en_es_flow",
            [
                "Hello, I need help with a refund.",
                "Hola, necesito un correo de confirmación de reembolso.",
                "Please continue in English.",
            ],
        ),
    ],
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Scrape Behavior/Voice only; skip test chat (faster when session blocked)",
    )
    args = parser.parse_args()
    config_only = args.config_only or os.getenv("GIFIC152_CONFIG_ONLY") == "1"

    report: dict = {
        "ticket": "GIFIC-152",
        "at": datetime.now(timezone.utc).isoformat(),
        "config_only": config_only,
        "agents": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
        )
        page = browser.new_context(permissions=["microphone"]).new_page()
        login(page)

        for key, (aid, name) in AGENTS.items():
            ag: dict = {"name": name, "agent_id": aid, "config": {}, "cases": []}
            for page_key in ("behavior", "voice"):
                url = f"{BASE}/organization/{ORG}/agent/{aid}/{page_key}"
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2.5)
                text = page.inner_text("body")
                ag["config"][page_key] = {
                    "allowed_languages_snip": _extract_section(text, "Allowed Languages"),
                    "default_language_snip": _extract_section(text, "Default Language"),
                    "stt": _grep_line(text, "STT"),
                    "tts": _grep_line(text, "TTS"),
                }

            if config_only:
                report["agents"][key] = ag
                continue

            test_url = f"{BASE}/organization/{ORG}/agent/{aid}/test"
            for cid, turns in CASES[key]:
                page.goto(test_url, wait_until="domcontentloaded", timeout=90000)
                time.sleep(2)
                for end_label in ("End Session", "End Call"):
                    end = page.locator(f"button:has-text('{end_label}')")
                    if end.count():
                        try:
                            end.first.click(timeout=3000)
                            time.sleep(2)
                            break
                        except Exception:
                            pass
                started = ensure_call_started(page)
                full = ""
                err = ""
                turn_log: list = []
                if not started:
                    err = "session_start_failed"
                    full = page.inner_text("body")
                else:
                    try:
                        for t in turns:
                            full = say(page, t)
                            ti2 = full.find("Transcript")
                            transcript = full[ti2 : ti2 + 12000] if ti2 >= 0 else full[-8000:]
                            turn_log.append(
                                {
                                    "caller": t,
                                    "signals": analyze(full, True),
                                    "transcript_tail": transcript[-4000:],
                                }
                            )
                    except Exception as exc:
                        err = str(exc)
                        full = page.inner_text("body")
                ag["cases"].append(
                    {
                        "id": cid,
                        "turns": turns,
                        "session_started": started,
                        "error": err,
                        "signals": analyze(full, True) if started else {},
                        "turns_detail": turn_log if started and not err else [],
                        "transcript": full[full.find("Transcript") : full.find("Transcript") + 15000]
                        if started and full.find("Transcript") >= 0
                        else full[-5000:],
                    }
                )
            report["agents"][key] = ag

        browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


def _extract_section(text: str, label: str) -> str:
    i = text.find(label)
    if i < 0:
        return ""
    return text[i : i + 400].replace("\n", " | ")


def _grep_line(text: str, label: str) -> str:
    for ln in text.splitlines():
        if label.lower() in ln.lower():
            return ln.strip()[:200]
    return ""


if __name__ == "__main__":
    raise SystemExit(main())