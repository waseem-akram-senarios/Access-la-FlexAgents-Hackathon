# Fix: `Agent not ready within 10s`

## What it means

LiveKit created a simulation job (`agent-AJ_…`) but **no agent process joined the sim room within 10 seconds**.

## Two different paths

| Path | What you need |
|------|----------------|
| `lk agent simulate … --agent-name flexagent.staging` | A **LiveKit Cloud Agent** deployed on this project (`lk agent list` shows an agent). FlexAgents staging uses this in production. |
| `lk agent simulate … --yes flexagent_staging_worker.py` | CLI **spawns** the worker for the run (works without Cloud deploy; agent becomes ready). |
| Dashboard **Test** / WebRTC rooms | A worker registered as `flexagent.staging` via `start` (see below). |

This repo had **no Cloud Agent** (`lk agent list` → empty) and **no worker** registered as `flexagent.staging`, so `--agent-name` always failed.

## Do NOT leave a worker registered as `flexagent.staging` on the shared project

That steals **dashboard WebRTC** calls from FlexAgents’ real staging worker.

**Stop it:**

```bash
bash eval/platform/stop_flexagent_staging_worker.sh
```

**Simulations (no dispatch steal):**

```bash
lk agent simulate --scenarios … --yes flexagent_staging_worker.py
```

Only if you explicitly need local `start` on the production name (rare):

```bash
ALLOW_STAGING_DISPATCH_COMPETITION=1 bash eval/platform/ensure_flexagent_staging_worker.sh
```

- Worker registers as `flexagent.staging` (`eval/staging/flexagent_staging_worker.py`).
- Log: `eval/reports/flexagent_staging_worker.log`
- Stop: `kill $(cat eval/reports/flexagent_staging_worker.pid)`

Voice flow runner calls this by default (`ACCESS_LA_ENSURE_WORKER=0` to skip).

## Fix (simulations with `--agent-name`): deploy Cloud Agent OR spawn

**Option A — spawn (immediate, repo twin):**

```bash
cd eval/staging && source ../../.env
lk agent simulate audio --scenarios ../scenarios/access_la_flows/flow_1_answers_only.yaml \
  --yes flexagent_staging_worker.py
```

`run_access_la_flows_voice.sh` does this automatically when `lk agent list` is empty.

**Option B — true hosted sim (same as Cloud dispatch):**

```bash
cd eval/staging
lk agent dockerfile . --overwrite   # ensure entrypoint is flexagent_staging_worker.py
lk agent create -y --secrets-file ../../.env
lk agent deploy -y
lk agent list   # must show an agent
ACCESS_LA_FORCE_HOSTED=1 bash eval/platform/run_access_la_flows_voice.sh
```

Requires LiveKit Cloud build/deploy permissions and inference/API secrets for STT/LLM/TTS.

## FlexAgents team

If FlexAgents already runs `flexagent.staging` on another cluster but sims still fail, their Cloud Agent may be **crashing on startup** (check LiveKit → Agents → logs). Your local `.env` `LIVEKIT_*` must be the **same project** FlexAgents uses for staging.