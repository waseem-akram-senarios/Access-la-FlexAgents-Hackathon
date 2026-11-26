#!/usr/bin/env bash
# DANGER on shared LiveKit projects: registering as flexagent.staging steals dashboard calls.
# Prefer: lk agent simulate ... --yes flexagent_staging_worker.py (no long-running worker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
AGENT_NAME="${LIVEKIT_REGISTER_AGENT_NAME:-flexagent.staging}"
PIDFILE="$ROOT/eval/reports/flexagent_staging_worker.pid"
LOG="$ROOT/eval/reports/flexagent_staging_worker.log"

if [[ "${ALLOW_STAGING_DISPATCH_COMPETITION:-0}" != "1" ]]; then
  echo "Refusing to start: would register as '$AGENT_NAME' on shared LiveKit and steal FlexAgents staging calls." >&2
  echo "Use text sim instead: lk agent simulate --scenarios <yaml> --yes flexagent_staging_worker.py" >&2
  echo "If you really need this: ALLOW_STAGING_DISPATCH_COMPETITION=1 bash $0" >&2
  exit 1
fi

mkdir -p "$ROOT/eval/reports"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
export LIVEKIT_REGISTER_AGENT_NAME="$AGENT_NAME"

worker_running() {
  [[ -f "$PIDFILE" ]] || return 1
  local pid
  pid=$(<"$PIDFILE")
  kill -0 "$pid" 2>/dev/null || return 1
}

if worker_running; then
  echo "Worker already running (pid $(<"$PIDFILE")), agent_name=$AGENT_NAME"
  exit 0
fi

cd "$STAGING"
nohup uv run python flexagent_staging_worker.py start >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "Started worker pid $(<"$PIDFILE"); agent_name=$AGENT_NAME; log: $LOG"
echo "Stop with: bash eval/platform/stop_flexagent_staging_worker.sh"