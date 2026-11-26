# Access LA — LiveKit sims (use the method that already passed)

**Baseline that worked in git (`f0a1045`):** see [`jenny_livekit_simulation_report.md`](../reports/jenny_livekit_simulation_report.md) — **9/10 PASS** with text sim + local worker.

| Field | Value |
|-------|--------|
| **Dashboard test** | [Access LA test](https://dashboard-staging.flexagents.ai/organization/6aa1562861347fe1a3087d63/agent/6af703a01d07b8f78656fe4f/test) |
| **organization_id** | `6aa1562861347fe1a3087d63` |
| **agent_id** | `6af703a01d07b8f78656fe4f` |

## ✅ Working (match git / report)

From repo root:

```bash
bash eval/platform/run_jenny_livekit_simulate.sh
```

Or one scenario:

```bash
cd eval/staging
set -a && source ../../.env && set +a
lk agent simulate \
  --scenarios ../scenarios/jenny_separate/01_kb.yaml \
  --yes flexagent_staging_worker.py
```

Four call-flow YAMLs (same method):

```bash
bash eval/platform/run_access_la_flows_text.sh
```

**Do not use** `--agent-name flexagent.staging` for sims — the report lists that as failing (*not ready within 10s*).

**Do not use** `simulate audio` for sign-off here — report lists *VAD never detects speech* in this environment.

## ⚠️ Experimental (not the 9/10 PASS path)

- `run_access_la_flows_voice.sh` — audio + hosted agent (blocked on this project)
- `ensure_flexagent_staging_worker.sh` — only needed for dashboard WebRTC / dispatch, not for text sim

Details: `FLEXAGENT_STAGING_WORKER.md`

Progress from voice attempts: [`access_la_flows_voice.md`](../reports/access_la_flows_voice.md)