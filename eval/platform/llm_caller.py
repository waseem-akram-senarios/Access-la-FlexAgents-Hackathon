"""LLM-simulated caller for FlexAgents Playwright tests (replaces LiveKit text sim user)."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from jenny_scenarios import load_scenario_block

DONE = "[DONE]"

CALLER_SYSTEM = """You simulate the HUMAN CALLER on a live phone call with Access LA (Jenny).
You are NOT the agent. Output ONLY what the caller says next — plain spoken English, usually one or two short sentences.
Rules:
- Follow the scenario instructions and facts exactly (phone 213-555-0199 when relevant).
- When the agent reads back details and asks for confirmation, say "Yes" unless the scenario says otherwise.
- When asked for date and time, give a FULL answer (e.g. yesterday at 2 PM on route 7, or November 5 at 2 PM on route 7).
- Never speak as the agent. No markdown, no labels, no quotes around the whole line.
- If the scenario success criteria are clearly met (both case numbers heard, callback booked, etc.), output exactly: [DONE]
- If the agent is closing ("anything else", "what would you like to do next") and goals are met, output [DONE].
"""


def _chat(messages: list[dict[str, str]]) -> str:
    base = (os.getenv("EVAL_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = os.getenv("OPENAI_API_KEY") or os.getenv("EVAL_LLM_API_KEY")
    if not key:
        raise RuntimeError(
            "Set OPENAI_API_KEY (or EVAL_LLM_API_KEY) for --caller llm. "
            "Optional: EVAL_LLM_BASE_URL for Ollama-compatible endpoints."
        )
    model = os.getenv("EVAL_CALLER_MODEL", "gpt-4.1-mini")
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.15,
        "max_tokens": 150,
    }
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90.0,
    )
    r.raise_for_status()
    data = r.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def normalize_reply(line: str) -> str:
    line = line.strip().strip('"').strip("'")
    if line.upper().startswith("CALLER:"):
        line = line.split(":", 1)[1].strip()
    if line.upper().startswith("YOU:"):
        line = line.split(":", 1)[1].strip()
    return line


def next_caller_line(
    case_id: str,
    transcript: str,
    pass_criteria: str,
    *,
    opening_sent: bool,
) -> str:
    instructions, expectations = load_scenario_block(case_id)
    user = f"""Case id: {case_id}
Pass criteria (for your planning only): {pass_criteria}

Caller scenario instructions:
{instructions or "(use pass criteria and transcript)"}

Agent expectations (what Jenny should do):
{expectations or pass_criteria}

Opening line already sent to the agent: {opening_sent}

Transcript so far (newest at bottom):
---
{transcript[-5000:]}
---

What should the caller say next? One line only, or {DONE} if finished."""
    raw = _chat(
        [
            {"role": "system", "content": CALLER_SYSTEM},
            {"role": "user", "content": user},
        ]
    )
    return normalize_reply(raw)


def should_stop_conversation(case_id: str, transcript: str) -> bool:
    t = transcript.lower()
    if re.search(r"what else can i help|anything else i can|is there anything else\b", t):
        return True
    if case_id == "JENNY-10" and ("won't file" in t or "not file" in t or "understood" in t):
        return True
    if case_id == "JENNY-7":
        saved = len(re.findall(r"has been saved", t))
        if saved >= 2:
            return True
    if case_id == "JENNY-5" and re.search(r"\bc\s+b\s*,|\bcb-|\bbooked\b", transcript, re.I):
        return True
    if case_id == "JENNY-6" and "cancel" in t and re.search(r"\bc\s+b\s*,|\bcb-", transcript, re.I):
        return True
    return False