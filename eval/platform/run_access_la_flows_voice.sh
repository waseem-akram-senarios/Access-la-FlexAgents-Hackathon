#!/usr/bin/env bash
# LiveKit AUDIO sim — 4 unique call flows, one yaml at a time.
# Hosted: flexagent.staging + org/agent in scenario userdata.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
REPORT="$ROOT/eval/reports/access_la_flows_voice.md"
LOG="$ROOT/eval/reports/access_la_flows_voice_$(date -u +%Y%m%dT%H%M%SZ).log"
AGENT_NAME="${LIVEKIT_AGENT_NAME:-flexagent.staging}"
WORKER="flexagent_staging_worker.py"
FALLBACK="${ACCESS_LA_WORKER_FALLBACK:-1}"

mkdir -p "$ROOT/eval/reports"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

# Text sim (9/10 PASS path) does not need this. Only for dashboard WebRTC:
if [[ "${ACCESS_LA_ENSURE_WORKER:-0}" == "1" ]]; then
  bash "$ROOT/eval/platform/ensure_flexagent_staging_worker.sh"
fi

cd "$STAGING"

FLOWS=(
  "1|Call 1 Answers only|../scenarios/access_la_flows/flow_1_answers_only.yaml"
  "2|Call 2 Lost item service|../scenarios/access_la_flows/flow_2_lost_item_service.yaml"
  "3|Call 3 Two jobs|../scenarios/access_la_flows/flow_3_two_jobs.yaml"
  "4|Call 4 Limits|../scenarios/access_la_flows/flow_4_limits.yaml"
)

cat >"$REPORT" <<HDR
# Access LA — LiveKit voice sim by call flow

**Agent:** \`6af703a01d07b8f78656fe4f\` · \`flexagent.staging\`  
**Command:** \`lk agent simulate audio --agent-name $AGENT_NAME\`  
**Log:** \`$LOG\`

| Flow | SCN | Status | SR / note |
|------|-----|--------|-----------|
HDR

has_cloud_agent() {
  lk agent list 2>/dev/null | grep -q .
}

run_flow() {
  local num="$1" label="$2" scen="$3"
  echo "======== FLOW $num: $label ========" | tee -a "$LOG"
  local status="FAIL" note="" sr=""
  local use_hosted=0
  if [[ "${ACCESS_LA_FORCE_HOSTED:-0}" == "1" ]] || has_cloud_agent; then
    use_hosted=1
  fi
  if [[ "$use_hosted" == "1" ]]; then
    if lk agent simulate audio --scenarios "$scen" --agent-name "$AGENT_NAME" 2>&1 | tee -a "$LOG"; then
      if tail -80 "$LOG" | grep -qE '1 passed, 0 failed|[0-9]+ passed, 0 failed'; then
        status="PASS"
        note="hosted audio"
      fi
    fi
  else
    echo "No LiveKit Cloud Agent (lk agent list empty); using spawned worker (avoids not-ready 10s)." | tee -a "$LOG"
    if lk agent simulate audio --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$LOG"; then
      if tail -80 "$LOG" | grep -qE '1 passed, 0 failed|[0-9]+ passed, 0 failed'; then
        status="PASS"
        note="spawned worker audio"
      fi
    fi
  fi
  local hosted_note="" local_fallback_note=""
  if tail -80 "$LOG" | grep -qi 'not ready within'; then
    hosted_note="hosted not ready 10s"
  fi
  if [[ "$status" != "PASS" && "$FALLBACK" == "1" && "$use_hosted" == "1" ]]; then
    echo "--- fallback local worker audio ---" | tee -a "$LOG"
    local log_before
    log_before=$(wc -l <"$LOG")
    if lk agent simulate audio --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$LOG"; then
      if tail -n +"$log_before" "$LOG" | grep -qE '1 passed, 0 failed'; then
        status="PASS"
        note="local worker audio (dev twin, not dashboard prompt)"
      elif tail -n +"$log_before" "$LOG" | grep -qi 'never detected caller'; then
        local_fallback_note="local audio: no caller speech (STT)"
      fi
    fi
  fi
  if [[ "$status" == "PASS" ]]; then
    :
  elif [[ -n "$local_fallback_note" ]]; then
    status="BLOCKED"
    note="${hosted_note:+$hosted_note; }$local_fallback_note"
  elif [[ -n "$hosted_note" ]]; then
    status="FAIL"
    note="$hosted_note"
  fi
  sr=$(grep -oE 'Run:[[:space:]]+SR_[a-zA-Z0-9]+' "$LOG" | tail -1 | awk '{print $2}' || true)
  scn=$(grep -oE 'SCN_flow_[a-z0-9_]+' "$scen" 2>/dev/null | head -1 || echo "SCN_flow_${num}")
  echo "| $num | $label | **$status** | ${sr:-—}; $note |" >>"$REPORT"
  echo "FLOW $num $status $note" | tee -a "$LOG"
  sleep 5
}

echo "# Flow voice run $(date -u -Iseconds)" | tee "$LOG"
for entry in "${FLOWS[@]}"; do
  IFS='|' read -r num label scen <<<"$entry"
  run_flow "$num" "$label" "$scen"
done
echo "" >>"$REPORT"
echo "Done. See \`$LOG\`" >>"$REPORT"
echo "Report: $REPORT"