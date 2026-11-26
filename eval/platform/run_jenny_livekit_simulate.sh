#!/usr/bin/env bash
# Same method as commit f0a1045 / eval/reports/jenny_livekit_simulation_report.md (9/10 PASS).
# Text sim + spawn local worker. No --agent-name. No audio.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
REPORT="$ROOT/eval/reports/jenny_livekit_simulation_$(date -u +%Y%m%dT%H%M%SZ).log"
WORKER="flexagent_staging_worker.py"

mkdir -p "$ROOT/eval/reports"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

SCENARIOS=(
  01_kb
  02_directory
  03_case_sms
  04_case_lookup
  05_callback_sms
  06_callback_cancel
  07_two_jobs
  08_complaint_line
  09_no_ride_booking
  10_caller_says_no
)

echo "# Jenny LiveKit simulate (text + local worker) $(date -u -Iseconds)" | tee "$REPORT"
echo "See: eval/reports/jenny_livekit_simulation_report.md for baseline 9/10 PASS run." | tee -a "$REPORT"
echo "" | tee -a "$REPORT"

pass=0
fail=0
for id in "${SCENARIOS[@]}"; do
  scen="../scenarios/jenny_separate/${id}.yaml"
  echo "======== $id ========" | tee -a "$REPORT"
  log_before=$(wc -l <"$REPORT")
  if lk agent simulate --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$REPORT"; then
    if tail -n +"$log_before" "$REPORT" | grep -qE '1 passed, 0 failed'; then
      ((pass++)) || true
      echo "[$id] PASS" | tee -a "$REPORT"
    else
      ((fail++)) || true
      echo "[$id] FAIL" | tee -a "$REPORT"
    fi
  else
    ((fail++)) || true
    echo "[$id] FAIL (exit)" | tee -a "$REPORT"
  fi
  echo "" | tee -a "$REPORT"
  sleep 2
done

echo "SUMMARY pass=$pass fail=$fail log=$REPORT" | tee -a "$REPORT"