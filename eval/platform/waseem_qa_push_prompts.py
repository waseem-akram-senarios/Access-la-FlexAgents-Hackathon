"""Push Waseem QA main + sub-agent instructions to staging dashboard."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

USER = os.getenv("FLEXAGENTS_USERNAME")
PW = os.getenv("FLEXAGENTS_PASSWORD")
BASE = "https://dashboard-staging.flexagents.ai"
ORG = "6aa1562861347fe1a3087d63"
AID = "6b095a096bf2d249020d06bd"
GREETING = (
    "Thanks for calling the Waseem QA Platform on staging. I'm your QA assistant. "
    "How can I help you today? Para español, hable en español. للعربية، تفضل بالعربية."
)
MAIN_PROMPT = (ROOT / "eval/staging/prompts/waseem_qa_platform.md").read_text(encoding="utf-8")

SUB_FILES = {
    "Email sending": ROOT / "eval/staging/prompts/waseem_qa_email_subagent.md",
    "Knowledge search": ROOT / "eval/staging/prompts/waseem_qa_knowledge_subagent.md",
}

SUB_IDS = {
    "Email sending": "6b095eea6bf2d249020d0ec5",
    "Knowledge search": "6b095e976bf2d249020d0e8c",
}

REPORT = ROOT / "eval/reports/waseem_qa_prompts_push.json"


def split_subagent_md(text: str) -> tuple[str, str]:
    parts = re.split(r"^# .+ — when to use.*\n", text, maxsplit=1, flags=re.M)
    rest = parts[-1] if len(parts) > 1 else text
    chunks = re.split(r"^# .+ — instructions.*\n", rest, maxsplit=1, flags=re.M)
    when = chunks[0].strip()
    instructions = chunks[1].strip() if len(chunks) > 1 else ""
    return when, instructions


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', USER or "")
    page.fill('input[type="password"]', PW or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def save_main_prompt(page, result: dict) -> None:
    page.goto(f"{BASE}/organization/{ORG}/agent/{AID}/prompt", wait_until="networkidle", timeout=90000)
    time.sleep(2)
    page.locator("button:has-text('Edit')").first.click()
    time.sleep(2)
    areas = page.locator("textarea")
    if areas.count() >= 2:
        areas.nth(0).fill(GREETING)
        areas.nth(1).fill(MAIN_PROMPT)
    save = page.locator("button:has-text('Save')").first
    if save.count() and not save.is_disabled():
        save.click()
        time.sleep(4)
        main_saved = "saved" in page.inner_text("body").lower()
    else:
        main_saved = "unchanged" if save.count() and save.is_disabled() else False
    result["main"] = {
        "saved": main_saved,
        "has_knowledge_search": "Knowledge search" in MAIN_PROMPT,
        "has_email_sending": "Email sending" in MAIN_PROMPT,
    }


def save_sub_agent(page, name: str, result: dict) -> None:
    when, instructions = split_subagent_md(SUB_FILES[name].read_text(encoding="utf-8"))
    sid = SUB_IDS[name]
    page.goto(
        f"{BASE}/organization/{ORG}/agent/{AID}/sub-agents/{sid}",
        wait_until="networkidle",
        timeout=90000,
    )
    time.sleep(2)
    for label in ("Edit", "Configure", "Update"):
        loc = page.locator(f"button:has-text('{label}')")
        if loc.count():
            loc.first.click()
            time.sleep(2)
            break
    else:
        # open from list
        page.goto(f"{BASE}/organization/{ORG}/agent/{AID}/sub-agents", wait_until="networkidle")
        time.sleep(2)
        page.get_by_text(name, exact=True).first.click()
        time.sleep(2)
        if page.locator("button:has-text('Edit')").count():
            page.locator("button:has-text('Edit')").first.click()
            time.sleep(2)

    areas = page.locator("textarea")
    n = areas.count()
    entry = {"name": name, "id": sid, "textarea_count": n}
    if n >= 2:
        areas.nth(0).fill(when)
        areas.nth(1).fill(instructions + "\n")
        entry["when_len"] = len(when)
        entry["instructions_len"] = len(instructions)
    elif n == 1:
        areas.nth(0).fill(f"{when}\n\n{instructions}")
        entry["combined_len"] = len(when) + len(instructions)

    save_btn = page.locator("button:has-text('Save')")
    if not save_btn.count():
        entry["saved"] = False
        entry["error"] = "No Save button"
    elif save_btn.first.is_disabled():
        entry["saved"] = False
        entry["error"] = "Save disabled"
        entry["body_hint"] = page.inner_text("body")[:500]
    else:
        save_btn.first.click()
        time.sleep(5)
        body_low = page.inner_text("body").lower()
        entry["saved"] = any(x in body_low for x in ("saved", "success", "changes saved"))
        if not entry["saved"]:
            entry["body_hint"] = page.inner_text("body")[:600]
    result["sub_agents"][name] = entry


def main() -> None:
    result: dict = {"sub_agents": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_context(viewport={"width": 1400, "height": 1400}).new_page()
        login(page)
        save_main_prompt(page, result)
        for name in SUB_FILES:
            save_sub_agent(page, name, result)
        browser.close()

    REPORT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()