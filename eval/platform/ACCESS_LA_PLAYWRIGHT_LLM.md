# Access LA — Playwright + LLM caller (LiveKit sim alternative)

When `lk agent simulate` / remote `flexagent.staging` is unavailable, run Jenny on the **FlexAgents Test Your Agent** page with an **LLM playing the caller**, using the same briefs as `eval/scenarios/jenny_separate/*.yaml`.

## Prerequisites

- `FLEXAGENTS_USERNAME` / `FLEXAGENTS_PASSWORD` in `.env`
- `OPENAI_API_KEY` (or `EVAL_LLM_API_KEY`) for the simulated caller
- Optional: `EVAL_CALLER_MODEL` (default `gpt-4.1-mini`)
- Optional: `EVAL_LLM_BASE_URL` (e.g. `http://127.0.0.1:11434/v1` for Ollama OpenAI-compatible API)

## Run

```bash
# All 10 cases, LLM caller (default)
bash eval/platform/run_access_la_playwright.sh

# One case
bash eval/platform/run_access_la_playwright.sh --ids JENNY-7

# Legacy regex replies (no API key)
bash eval/platform/run_access_la_playwright.sh --caller regex
```

Reports: `eval/reports/access_la_playwright_latest.json` (includes `caller_mode`).

## How it works

| Piece | Role |
|--------|------|
| Playwright | Login, Start Call, type messages |
| `jenny_scenarios.py` | Maps JENNY-* → YAML instructions |
| `llm_caller.py` | Next caller utterance from transcript + YAML |
| `judge()` in runner | Same rule-based pass/fail (optional LLM judge later) |

## vs LiveKit sim

- **Pros:** Real staging worker, job metadata via dashboard, same UI as manual tests.
- **Cons:** Slower, needs OpenAI key, rule judge can still disagree with LLM caller (tune judges or add `--judge llm` later).