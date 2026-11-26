#!/usr/bin/env bash
# LiveKit sim against REMOTE FlexAgents worker only (no local --yes worker).
# Your laptop only calls LiveKit Cloud API; the agent must run on FlexAgents infra.
#
# Requires: remote worker registered as flexagent.staging on the project in LIVEKIT_URL.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
SCEN="${1:-../scenarios/jenny_separate/01_kb.yaml}"
AGENT_NAME="${LIVEKIT_AGENT_NAME:-flexagent.staging}"
CLOUD_AGENT_ID="${LIVEKIT_CLOUD_AGENT_ID:-A_hU8Z9V5mofda}"
DEPLOY="${LIVEKIT_AGENT_DEPLOYMENT:-}"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

if pgrep -f 'flexagent_staging_worker.py start' >/dev/null; then
  echo "Stop local worker first (steals dispatch): bash eval/platform/stop_flexagent_staging_worker.sh" >&2
  exit 1
fi

extra=()
[[ -n "$DEPLOY" ]] && extra+=(--deployment "$DEPLOY")

echo "Project: $LIVEKIT_URL"
echo "LiveKit Cloud agent id: $CLOUD_AGENT_ID (verify: lk agent status --id $CLOUD_AGENT_ID)"
echo "Dispatch name: $AGENT_NAME deployment: ${DEPLOY:-production}"
echo "Scenario: $SCEN"
if ! lk agent status --id "$CLOUD_AGENT_ID" 2>&1 | grep -qv "no agents found"; then
  echo "WARNING: Cloud agent $CLOUD_AGENT_ID not visible with this LIVEKIT_* project — sim may fail." >&2
  echo "See eval/platform/REMOTE_FLEXAGENT_STAGING_SIM.md" >&2
fi
exec lk agent simulate text --agent-name "$AGENT_NAME" "${extra[@]}" --scenarios "$SCEN"