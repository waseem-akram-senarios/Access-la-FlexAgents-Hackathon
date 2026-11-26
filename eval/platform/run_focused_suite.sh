#!/usr/bin/env bash
# Focused platform LiveKit suite — run from repo root:
#   bash eval/platform/run_focused_suite.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
REPORT="$ROOT/eval/reports/platform_livekit_focused_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$ROOT/eval/reports"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

cd "$STAGING"

# F-ID | SCN yaml (under eval/scenarios) | worker
TESTS=(
  "F0|../scenarios/ana_separate/02_access_program_17.yaml|ana_worker.py"
  "F8|../scenarios/neo_separate/05_saturday.yaml|neo_worker.py"
  "F3|../scenarios/neo_separate/04_route_serves_stop.yaml|neo_worker.py"
  "F4|../scenarios/neo_separate/02_where_scheduled.yaml|neo_worker.py"
  "F5|../scenarios/neo_separate/08_realtime_late.yaml|neo_worker.py"
  "F6|../scenarios/neo_separate/03_routes_at_stop.yaml|neo_worker.py"
  "F7|../scenarios/jenny_separate/04_case_lookup.yaml|flexagent_staging_worker.py"
  "F1|../scenarios/ana_separate/01_no_profile.yaml|ana_worker.py"
)

echo "# Platform focused LiveKit run $(date -u -Iseconds)" | tee "$REPORT"
echo "NOTE: neo/jenny/ana workers use local mocks — P-04/P-05 gate requires FlexAgents staging Neo." | tee -a "$REPORT"
echo "" | tee -a "$REPORT"

pass=0
fail=0
for entry in "${TESTS[@]}"; do
  IFS='|' read -r fid scen worker <<<"$entry"
  echo "======== $fid ========" | tee -a "$REPORT"
  if lk agent simulate --scenarios "$scen" --yes "$worker" 2>&1 | tee -a "$REPORT"; then
  if tail -30 "$REPORT" | grep -qE '1 passed, 0 failed|passed, 0 failed'; then
      ((pass++)) || true
      echo "[$fid] tally: PASS" | tee -a "$REPORT"
    else
      ((fail++)) || true
      echo "[$fid] tally: FAIL (ambiguous)" | tee -a "$REPORT"
    fi
  else
    ((fail++)) || true
    echo "[$fid] tally: FAIL (exit code)" | tee -a "$REPORT"
  fi
  echo "" | tee -a "$REPORT"
done

echo "SUMMARY pass=$pass fail=$fail log=$REPORT" | tee -a "$REPORT"