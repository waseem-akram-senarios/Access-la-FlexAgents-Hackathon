# Platform in-depth testing plan

**Priority:** Shared platform (P-01–P-07), not bot SOP.  
**Order:** **Phase 1 — LiveKit** (primary) → **Phase 2 — Playwright** (session / transfer / language).  
**QA reference:** Agent QA & Testing Evaluation Report + appendix P-01–P-07.

---

## North star

Prove **voice platform + GTFS/stop services + sim harness** before investing in full per-bot LiveKit suites.

**Platform ready gate (LiveKit):**

- Neo Knight cluster: `SCN_neo_4`, `neo_2`, `neo_8` **Pass × 2 consecutive** runs on **staging** (real backends, not local mocks).
- Harness: `SCN_ana_2_access` has full transcript (P-07).
- Evidence: every run logged with `SCN_*` + `SR_*`.

---

## Platform defects under test

| ID   | What | LiveKit | Playwright (Phase 2) |
|------|------|---------|----------------------|
| P-01 | Language switch without request | Voice sim (partial if text-only) | Primary |
| P-02 | Wrong / ignored caller phone | userdata variants | Primary |
| P-03 | Transfer announced, no handoff | Usually N/A in sim | Primary |
| P-04 | Stop wrong region / not found | Neo SCNs + tool payloads | Smoke |
| P-05 | GTFS / realtime / 404 / ETA | Neo SCNs | Smoke |
| P-06 | 30-turn limit / loops | `SCN_neo_3_which` | — |
| P-07 | Missing sim transcript | `SCN_ana_2_access` | — |

**Rule:** Do **not** use `eval/staging/neo_worker.py` mocks alone for P-04/P-05 sign-off — mocks always return Knight. Use **FlexAgents dashboard staging** simulations.

---

## Phase 0 — Setup (2–3 days)

- [ ] Staging access: all four agents (test + simulation).
- [ ] Baseline fails from QA doc:  
  `SR_rfpDDMmtLZ6J`, `SR_txnzXpcNvUw5`, `SR_gUgwH6yvkzWJ`, `SR_V7Li9QEpcs3d`, `SR_oUWZziobVUqR`
- [ ] Evidence sheet columns:  
  `Date | Env | P-ID | SCN | SR | Agent | Pass/Fail | Turns | ToolErrors | Stop/Phone | Note`
- [ ] Confirm Neo sim hits **staging GTFS/stop APIs** (not local worker mock).
- [ ] Optional same-day **API curl** for Knight Street + Route 1 (parallel to sims).

**Agent IDs (human / dashboard):**

| Agent  | Organization ID           | Agent ID                  |
|--------|---------------------------|---------------------------|
| Amelia | `6af96a0fbdbf32a95ff4651b` | `6af97679bdbf32a95ff46702` |
| Neo    | `6af72a3c4431b640e6041707` | `6af72aab4431b640e6041709` |
| Jenny  | (see `eval/scenarios/jenny_livekit.yaml`) | `6af703a01d07b8f78656fe4f` |

---

## Phase 1 — LiveKit platform testing (~3 weeks)

### Execution channels

1. **Channel A (sign-off):** FlexAgents dashboard voice simulation → `SCN_*` / `SR_*` (matches QA report).
2. **Channel B (dev):** Local `eval/staging/*_worker.py` + `eval/scenarios/*_separate/*.yaml` — re-validate on A before gate.

---

### Suite LK-PLAT-0 — Harness first (Day 1)

| Case | SCN | P-ID | Pass |
|------|-----|------|------|
| H1 | `SCN_ana_2_access` | P-07 | Transcript complete; fail only on behavior |
| H2 | `SCN_neo_5_saturday` | — | SR exported; logs accessible |
| H3 | Re-run H1 ×3 | — | ≤1 flake |

Repo: `eval/scenarios/ana_separate/02_access_program_17.yaml`

---

### Suite LK-PLAT-A — GTFS / stops / realtime (Neo) — critical path

Run on **staging**. Review **tool timeline** every run (404, wrong stop, deny serve).

| Order | SCN | YAML under `eval/scenarios/neo_separate/` | P-ID | Baseline SR |
|------:|-----|-------------------------------------------|------|-------------|
| 1 | `SCN_neo_5_saturday` | `05_saturday.yaml` | — | control |
| 2 | `SCN_neo_1_next` | `01_next_route.yaml` | — | control |
| 3 | `SCN_neo_4_serves` | `04_route_serves_stop.yaml` | P-04, P-05 | `SR_gUgwH6yvkzWJ` |
| 4 | `SCN_neo_2_where` | `02_where_scheduled.yaml` | P-05 | `SR_rfpDDMmtLZ6J` |
| 5 | `SCN_neo_8_late` | `08_realtime_late.yaml` | P-05 | `SR_V7Li9QEpcs3d` |
| 6 | `SCN_neo_3_which` | `03_routes_at_stop.yaml` | P-06 | `SR_txnzXpcNvUw5` |
| 7 | `SCN_neo_7_after` | `07_follow_up.yaml` | — | context |
| 8 | `SCN_neo_9_detour` | `09_detour.yaml` | P-05 | alerts |
| 9 | `SCN_neo_10_missed` | `10_missed_bus.yaml` | P-05 | — |

**Manual assertions (steps 3–6):**

- Stop = **BFT / Knight Street Transit Center (WA)** — not Michigan “Knights Inn”.
- Route 1 **serves** Knight when tool says yes.
- Late query includes **predicted arrival** when API supports it.
- `neo_3`: answer Routes 1, 2, 4 **or** bounded turns without loop.

**Regression:** Steps 3–6 must **Pass twice in a row** after any platform deploy.

---

### Suite LK-PLAT-B — Orchestration / session (cross-agent)

| Order | SCN | Agent | P-ID | Repo YAML |
|------:|-----|-------|------|-----------|
| 1 | `SCN_jenny_4_list_cases` | Jenny | orchestration | `jenny_separate/04_case_lookup.yaml` |
| 2 | `SCN_jenny_2_lost_bag` | Jenny | — | `jenny_separate/02_directory.yaml` |
| 3 | `SCN_ana_1_no_profile` | Ana | — | `ana_separate/01_no_profile.yaml` |
| 4 | `SCN_ana_3_no_rider_id` | Ana | — | `ana_separate/03_program_minus_one.yaml` |

**P-02 (if platform supports userdata):**

- α: `caller_phone: 2135550199` → tools use 213-555-0199  
- β: persona states different number → stated number wins after confirm  

If unsupported, mark P-02 **LiveKit incomplete** → Phase 2.

---

### Suite LK-PLAT-C — Language (P-01)

Voice simulation required (text-only sim is weak).

- Same pattern on **four agents**: English-only persona, 3 turns → no unprompted language switch.
- Compare Jenny human pattern: Spanish after English on L&F (`6affe928…`).

---

### Suite LK-PLAT-D — Reliability

- Re-run LK-PLAT-A steps **3–6** **3×** in 24h → flake ≤ 10%.
- Log turn count p95 for `SCN_neo_3_which`.

---

### Suite LK-PLAT-E — Transfer (P-03)

- If sim supports transfer: one case per agent that offers it.
- Else: **N/A on LiveKit** — mandatory in Playwright.

---

## Day 1 run list (start here)

1. `SCN_ana_2_access`  
2. `SCN_neo_5_saturday`  
3. `SCN_neo_4_serves`  
4. `SCN_neo_2_where`  
5. `SCN_neo_8_late`  
6. `SCN_neo_3_which`  
7. `SCN_jenny_4_list_cases`  
8. `SCN_ana_1_no_profile`  
9. **Re-run 3–6 once**

---

## Week-by-week schedule

| Week | Focus |
|------|--------|
| 0 | Phase 0 checklist |
| 1 | LK-PLAT-0 + LK-PLAT-A (3–6 daily until 2× Pass) |
| 2 | LK-PLAT-A (7–9) + LK-PLAT-B |
| 3 | LK-PLAT-C + LK-PLAT-D + regression 2× |
| 4 | Platform sign-off report → start Playwright |

---

## Phase 2 — Playwright (after LiveKit gate)

Scripts pattern: `eval/run_10_questions_web.py` + `.env` (`FLEXAGENTS_USERNAME`, `FLEXAGENTS_PASSWORD`, `FLEXAGENTS_TEST_URL` per agent).

| Test ID | P-ID | Agents | Purpose |
|---------|------|--------|---------|
| PF-LANG-01 | P-01 | All 4 | No unprompted language switch |
| PF-PHONE-01 | P-02 | Jenny, Ana | Stated phone overrides ANI |
| PF-PHONE-02 | P-02 | Jenny | Wrong phone then correct (512 vs 213…) |
| PF-XFER-01 | P-03 | Ana, Amelia | Transfer completes or honest fail |
| PF-GTFS-SMOKE-01 | P-04/P-05 | Neo | No MI stop names on Knight questions |

---

## Deliverables

1. **Platform matrix:** P-01–P-07 × Pass | Fail | N/A × `SR_*` / call ref  
2. **Jira:** one ticket per open P-ID (no duplicate platform + bot rows)  
3. **Regression list:** SCN order above + repo YAML paths  
4. **Gaps:** items deferred to Playwright or API-only  

---

## Re-run triggers

Full **LK-PLAT-A (3–6)** + **jenny_4** after changes to:

- Stop search / geocoder / GTFS feed  
- LiveKit turn limits or sim harness  
- Global STT/TTS/LLM or session/ANI layer  

---

## Related repo docs

- `EVAL.md` — eval framework levels; staging URLs (dashboard not in CI)  
- `eval/scenarios/*_separate/` — LiveKit scenario definitions  
- `eval/staging/team1_api_test.py` — API contracts (directory/transfer honesty; Track B)  
- QA Google Doc — human baselines and call IDs  

## Automated focused LiveKit suite (local)

```bash
cd eval/staging && uv sync
cd ../.. && bash eval/platform/run_focused_suite.sh
```

Latest summary: `eval/reports/platform_focused_summary.md` (full log: `platform_livekit_focused_*.log`).

Uses `lk agent simulate` + staging workers. **Does not replace** dashboard Neo runs for P-04/P-05 on real GTFS.