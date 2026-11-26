# Ana — GTA staging test (Playwright)

**URL:** https://dashboard-staging.flexagents.ai/organization/6af9699dbdbf32a95ff46515/agent/6af96f45bdbf32a95ff46533/test

## What this covers

| Group | IDs | Source |
|-------|-----|--------|
| GTA 25 Nov 2026 | `GTA-1` … `GTA-4` | Bot issues (wrong date, booking confusion, time help, DART client ID loop) |
| QA matrix | `N-01` … `N-14` | LiveKit + human call evidence from QA report |

Cases live in `eval/scenarios/ana_gta_playwright.json`. Runner: `eval/platform/run_ana_gta_playwright.py`.

## Prerequisites

- `.env`: `FLEXAGENTS_USERNAME`, `FLEXAGENTS_PASSWORD`
- Chromium for Playwright (`bash eval/platform/run_ana_gta_playwright.sh` installs if missing)

## Commands

```bash
# Full suite (~20–40 min)
bash eval/platform/run_ana_gta_playwright.sh

# GTA issues only
bash eval/platform/run_ana_gta_playwright.sh --group gta_25nov

# QA N-cases only
bash eval/platform/run_ana_gta_playwright.sh --group qa_matrix

# Single case
bash eval/platform/run_ana_gta_playwright.sh --ids GTA-4,N-01
```

## Outputs

- `eval/reports/ana_gta_playwright_latest.json` — full transcripts tail + status
- `eval/reports/ana_gta_playwright_latest.md` — summary table

## Limits

- **Text chat** on the test page (not full PSTN). Voice/STT paths are not asserted.
- Judges are **heuristic**; `PARTIAL` = needs human read of JSON transcript.
- Staging **phone fixtures** (213-555-014x) may differ from production GTA data — compare with LiveKit `eval/scenarios/ana_separate/*.yaml` for sign-off.

## LiveKit parity

For judged sims with `SR_*` IDs, still use:

```bash
lk agent simulate text --scenarios eval/scenarios/ana_separate/01_no_profile.yaml --yes eval/staging/ana_worker.py
```

Playwright is **Phase 2** in `PLATFORM_TESTING_PLAN.md` (dashboard / session / transfer), complementary to sims.