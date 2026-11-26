#!/usr/bin/env bash
# Reliable LiveKit sims for Access LA flows (TEXT — tests agent logic, not mic/STT).
# Does NOT use --agent-name (requires LiveKit Cloud Agent). Spawns repo worker per run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
REPORT="$ROOT/eval/reports/access_la_flows_text.md"
LOG="$ROOT/eval/reports/access_la_flows_text_$(date -u +%Y%m%dT%H%M%SZ).log"
WORKER="flexagent_staging_worker.py"

mkdir -p "$ROOT/eval/reports"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

FLOWS=(
  "1|Call 1 Answers only|../scenarios/access_la_flows/flow_1_answers_only.yaml"
  "2|Call 2 Lost item service|../scenarios/access_la_flows/flow_2_lost_item_service.yaml"
  "3|Call 3 Two jobs|../scenarios/access_la_flows/flow_3_two_jobs.yaml"
  "4|Call 4 Limits|../scenarios/access_la_flows/flow_4_limits.yaml"
)

cat >"$REPORT" <<HDR
# Access LA — LiveKit **text** sim (working path)

Use this when voice/audio sim is blocked on STT. Command:

\`lk agent simulate --scenarios <yaml> --yes $WORKER\`

**Log:** \`$LOG\`

| Flow | Status | SR / note |
|------|--------|-----------|
HDR

for entry in "${FLOWS[@]}"; do
  IFS='|' read -r num label scen <<<"$entry"
  echo "======== FLOW $num: $label ========" | tee -a "$LOG"
  status="FAIL"
  note=""
  log_before=$(wc -l <"$LOG")
  if lk agent simulate --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$LOG"; then
    if tail -n +"$log_before" "$LOG" | grep -qE '1 passed, 0 failed'; then
      status="PASS"
      note="text sim"
    elif tail -n +"$log_before" "$LOG" | grep -qE '0 passed, 1 failed|1 failed'; then
      note="judge fail (see log)"
    fi
  fi
  if tail -n +"$log_before" "$LOG" | grep -qi 'not ready within'; then
    status="FAIL"
    note="not ready (unexpected in spawn mode)"
  fi
  sr=$(grep -oE 'Run:[[:space:]]+SR_[a-zA-Z0-9]+' "$LOG" | tail -1 | awk '{print $2}' || true)
  echo "| $num | **$status** | ${sr:-—}; $note |" >>"$REPORT"
  sleep 3
done

echo "" >>"$REPORT"
echo "Done." >>"$REPORT"
echo "Report: $REPORT"