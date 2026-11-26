# Simulate remote Jenny — `flexagent.staging` / `A_hU8Z9V5mofda`

## Job metadata (not userdata) — remote dispatch works

**`lk agent simulate` does not set `job.metadata`.** Use explicit dispatch:

```bash
bash eval/platform/dispatch_flexagent_staging_job_metadata.sh
```

JSON: `eval/scenarios/flexagent_staging_job_metadata.json`  
→ `lk dispatch create --new-room --agent-name flexagent.staging --metadata '<json>'`

Remote agent **joins** the room when job metadata has org + agent (e.g. `room-8poYRNYH6bHb`, `agent-AJ_d3mxfJZGaU86`).

For **judged** simulations, LiveKit still cannot pass job metadata; FlexAgents must patch sim startup or you test via Console in that room.

## Two different “agent IDs”

| ID | What it is |
|----|------------|
| `6af703a01d07b8f78656fe4f` | **FlexAgents** dashboard agent (org `6aa1562861347fe1a3087d63`) — goes in scenario **userdata** |
| `A_hU8Z9V5mofda` | **LiveKit Cloud Agent** record — manage with `lk agent status/logs --id A_hU8Z9V5mofda` |

**Simulations dispatch by worker name**, not by `A_…`:

```bash
lk agent simulate text --agent-name flexagent.staging --scenarios <yaml>
```

Do **not** use `--yes flexagent_staging_worker.py` if you want the **remote** deploy only.

## Run (from repo)

```bash
cd eval/staging
set -a && source ../../.env && set +a
bash ../../eval/platform/run_remote_staging_sim.sh \
  ../scenarios/jenny_separate/01_kb.yaml
```

## Your `.env` must be the **same LiveKit project** as agent `A_hU8Z9V5mofda`

With current keys we see:

- `lk agent list` → empty  
- `lk agent status --id A_hU8Z9V5mofda` → **no agents found**  
- `lk agent versions --id A_hU8Z9V5mofda` → **failed to get agent**

So either the agent lives in **another** LiveKit project/team, or these API keys cannot read Cloud Agents.

**Fix:**

1. In [LiveKit Cloud](https://cloud.livekit.io) open the project where **Agents** shows `A_hU8Z9V5mofda` / `flexagent.staging`.
2. Copy that project’s **URL, API key, API secret** into `.env` as `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
3. Verify:  
   `lk agent status --id A_hU8Z9V5mofda`  
   should show deployments/workers (not “no agents found”).
4. Re-run `run_remote_staging_sim.sh`.

Or: `lk cloud auth` and select that project, then run sims.

## Why “not ready 10s” + metadata (important)

LiveKit documents that **Agent Simulations do not set job metadata, room metadata, or participant attributes**. Only scenario **`userdata`** is passed (via `ctx.simulation_context()`).

| Path | What gets org + agent |
|------|------------------------|
| **FlexAgents dashboard / Console test** | Usually **job metadata** (or token `RoomAgentDispatch` + JSON) when the room is created |
| **`lk agent simulate --agent-name flexagent.staging`** | **Dispatch by name only** — no job metadata; org/agent must come from **simulation userdata** in the worker code |
| **Your YAML `userdata`** | Correct for sims **only if** the **remote** FlexAgents worker reads `simulation_context().userdata()` |

If the cloud worker **only** reads `ctx.job.metadata` and **exits or hangs** when `organization_id` / `agent_id` are missing, sim jobs never become “ready” → **`not ready within 10s`**. That matches the **Dispatch errors** spike on the `flexagent.staging` overview chart.

**FlexAgents fix (on their worker, not in this repo):**

```python
# Pseudocode for entrypoint
sim = ctx.simulation_context()
if sim is not None:
    ud = sim.userdata()  # organization_id, agent_id from YAML
    load_flexagents_config(ud["organization_id"], ud["agent_id"])
else:
    meta = json.loads(ctx.job.metadata or "{}")
    load_flexagents_config(meta["organization_id"], meta["agent_id"])
```

Until that exists, remote sims can fail even when YAML userdata is correct.

## If sim still says “not ready within 10s”

The Cloud Agent exists but the **worker** is not joining sim rooms — check in LiveKit:

- Agent **logs** for `A_hU8Z9V5mofda`
- Production worker running and registered as **`flexagent.staging`**
- No crash on startup for job `agent-AJ_…`

Latest failed run example: `SR_bvWH29zZpDyi` — view with  
`lk agent simulate view SR_bvWH29zZpDyi`