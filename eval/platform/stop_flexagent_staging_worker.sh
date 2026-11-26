#!/usr/bin/env bash
# Unregister local worker from LiveKit (stop stealing flexagent.staging dispatch).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIDFILE="$ROOT/eval/reports/flexagent_staging_worker.pid"

stop_pid() {
  local pid=$1
  pkill -P "$pid" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
}

if [[ -f "$PIDFILE" ]]; then
  stop_pid "$(<"$PIDFILE")"
  rm -f "$PIDFILE"
fi
pkill -f 'flexagent_staging_worker.py start' 2>/dev/null || true
echo "Stopped local flexagent_staging_worker (if any was running)."
echo "FlexAgents staging dispatch should go back to their worker within a few seconds."