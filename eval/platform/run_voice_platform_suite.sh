#!/usr/bin/env bash
# Platform tests via full audio pipeline (LiveKit simulate audio).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
REPORT="$ROOT/eval/reports/platform_voice_livekit_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$ROOT/eval/reports"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

TESTS=(
  "V-F3|../scenarios/neo_separate/04_route_serves_stop.yaml|neo_worker.py|P-04"
  "V-F5|../scenarios/neo_separate/08_realtime_late.yaml|neo_worker.py|P-05"
  "V-F6|../scenarios/neo_separate/03_routes_at_stop.yaml|neo_worker.py|P-06"
  "V-F7|../scenarios/jenny_separate/02_directory.yaml|flexagent_staging_worker.py|orchestration"
  "V-P01|../scenarios/jenny_separate/02_directory.yaml|flexagent_staging_worker.py|P-01"
)

echo "# LiveKit AUDIO platform run $(date -u -Iseconds)" | tee "$REPORT"
for entry in "${TESTS[@]}"; do
  IFS='|' read -r vid scen worker pid <<<"$entry"
  echo "======== $vid ($pid) ========" | tee -a "$REPORT"
  if lk agent simulate audio --scenarios "$scen" --yes "$worker" 2>&1 | tee -a "$REPORT"; then
    if tail -40 "$REPORT" | grep -qE '[0-9]+ passed, 0 failed'; then
      echo "[$vid] PASS" | tee -a "$REPORT"
    else
      echo "[$vid] FAIL or ambiguous" | tee -a "$REPORT"
    fi
  else
    echo "[$vid] FAIL (exit)" | tee -a "$REPORT"
  fi
done
echo "Log: $REPORT"