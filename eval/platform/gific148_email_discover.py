#!/usr/bin/env python3
"""Discover staging agents/sub-agents mentioning email (GIFIC-148 setup)."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
BASE = "https://dashboard-staging.flexagents.ai"
EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASSWORD = os.getenv("FLEXAGENTS_PASSWORD")
OUT = ROOT / "eval/reports/gific148_discover.json"

# Known orgs from eval/staging/agents.json
SEED_ORGS = [
    ("Access LA", "6aa1562861347fe1a3087d63", "6af703a01d07b8f78656fe4f"),
    ("Barwood", "6af96a0fbdbf32a95ff4651b", "6af97679bdbf32a95ff46702"),
    ("Neo org", "6af72a3c4431b640e6041707", "6af72aab4431b640e6041709"),
    ("GTA Ana", "6af9699dbdbf32a95ff46515", "6af96f45bdbf32a95ff46533"),
]


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
    page.fill('input[type="email"]', EMAIL or "")
    page.fill('input[type="password"]', PASSWORD or "")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(2)


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("Missing FLEXAGENTS credentials", file=sys.stderr)
        return 2

    findings: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        login(page)

        for label, org_id, agent_id in SEED_ORGS:
            for suffix, name in (("sub-agents", "sub_agents"), ("integration", "integration"), ("tools", "tools")):
                url = f"{BASE}/organization/{org_id}/agent/{agent_id}/{suffix}"
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    time.sleep(1.5)
                    text = page.inner_text("body").lower()
                    hits = [w for w in ("email", "mail", "template", "send_email") if w in text]
                    if hits:
                        findings.append({"org": label, "org_id": org_id, "agent_id": agent_id, "page": name, "url": url, "keywords": hits})
                except Exception as exc:
                    findings.append({"org": label, "page": name, "error": str(exc)[:200]})

        browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"findings": findings}, indent=2), encoding="utf-8")
    print(json.dumps(findings, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())