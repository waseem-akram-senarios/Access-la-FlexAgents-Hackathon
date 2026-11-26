#!/usr/bin/env bash
# Dispatch remote flexagent.staging with real job metadata (ctx.job.metadata).
# This is NOT lk agent simulate — sims cannot pass job metadata per LiveKit docs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
META_FILE="${1:-$ROOT/eval/scenarios/flexagent_staging_job_metadata.json}"
AGENT_NAME="${LIVEKIT_AGENT_NAME:-flexagent.staging}"
DEPLOY="${LIVEKIT_AGENT_DEPLOYMENT:-}"
ROOM="${LIVEKIT_TEST_ROOM:-}"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

if pgrep -f 'flexagent_staging_worker.py start' >/dev/null; then
  echo "Stop local worker first: bash eval/platform/stop_flexagent_staging_worker.sh" >&2
  exit 1
fi

META=$(python3 -c "import json; print(json.dumps(json.load(open('$META_FILE'))))")
extra=()
[[ -n "$DEPLOY" ]] && extra+=(--deployment "$DEPLOY")

if [[ -n "$ROOM" ]]; then
  echo "Dispatching $AGENT_NAME to room $ROOM with job metadata..."
  lk dispatch create --room "$ROOM" --agent-name "$AGENT_NAME" "${extra[@]}" --metadata "$META" --json
else
  echo "Dispatching $AGENT_NAME to new room with job metadata..."
  lk dispatch create --new-room --agent-name "$AGENT_NAME" "${extra[@]}" --metadata "$META" --json
fi

echo ""
echo "Metadata file: $META_FILE"
echo "Talk in room via FlexAgents test page or LiveKit Agents Console for that room."
echo "For judged sims: LiveKit does not support job metadata in lk agent simulate — FlexAgents must read sim userdata OR you use this dispatch path."