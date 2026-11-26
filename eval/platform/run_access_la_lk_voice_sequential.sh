#!/usr/bin/env bash
# Access LA — LiveKit voice sims ONLY, one yaml at a time. No Playwright.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
PROGRESS="$ROOT/eval/reports/access_la_voice_sim_sequential.md"
LOG="$ROOT/eval/reports/lk_voice_sequential_$(date -u +%Y%m%dT%H%M%SZ).log"
# Must match eval/scenarios/access_la_staging_agent.json
CLOUD_AGENT="${LIVEKIT_AGENT_NAME:-flexagent.staging}"
ORG_ID="6aa1562861347fe1a3087d63"
AGENT_ID="6af703a01d07b8f78656fe4f"
HOSTED_ONLY="${ACCESS_LA_HOSTED_ONLY:-0}"
WORKER="flexagent_staging_worker.py"
mkdir -p "$ROOT/eval/reports"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

YAMLS=(
  "4|V-KB|../scenarios/jenny_separate/01_kb.yaml"
  "5|V-KB-2|../scenarios/jenny_separate/01_kb.yaml"
  "28|SIM-02|../scenarios/jenny_separate/02_directory.yaml"
  "29|SIM-03|../scenarios/jenny_separate/03_case_sms.yaml"
  "30|SIM-04|../scenarios/jenny_separate/04_case_lookup.yaml"
  "31|SIM-05|../scenarios/jenny_separate/05_callback_sms.yaml"
  "32|SIM-06|../scenarios/jenny_separate/06_callback_cancel.yaml"
  "33|SIM-07|../scenarios/jenny_separate/07_two_jobs.yaml"
  "34|SIM-08|../scenarios/jenny_separate/08_complaint_line.yaml"
  "35|SIM-09|../scenarios/jenny_separate/09_no_ride_booking.yaml"
  "36|SIM-10|../scenarios/jenny_separate/10_caller_says_no.yaml"
)

append_row() {
  local seq="$1" cid="$2" status="$3" note="$4"
  local row="| $seq | $cid | **$status** | $note |"
  printf '%s\n' "$row" >> "$PROGRESS"
}

run_one() {
  local seq="$1" cid="$2" scen="$3"
  echo "======== SEQ $seq $cid ========" | tee -a "$LOG"
  local status="FAIL" note=""
  local sr=""
  # 1) Try hosted LiveKit agent (matches staging FlexAgents voice path)
  if lk agent simulate audio --scenarios "$scen" --agent-name "$CLOUD_AGENT" 2>&1 | tee -a "$LOG"; then
    if tail -60 "$LOG" | grep -qE '[0-9]+ passed, 0 failed|1 passed, 0 failed'; then
      status="PASS"
      note="cloud:$CLOUD_AGENT"
    else
      note="cloud ambiguous"
    fi
  fi
  if [[ "$status" != "PASS" ]]; then
    if tail -30 "$LOG" | grep -qi 'not ready within'; then
      note="cloud agent not ready org=$ORG_ID agent=$AGENT_ID name=$CLOUD_AGENT"
    elif tail -30 "$LOG" | grep -qi 'never detected caller'; then
      note="STT no caller speech"
      status="BLOCKED"
    fi
  fi
  if [[ "$status" != "PASS" && "$HOSTED_ONLY" != "1" ]]; then
    echo "--- fallback local worker $WORKER (not dashboard agent) ---" | tee -a "$LOG"
    if lk agent simulate audio --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$LOG"; then
      if tail -40 "$LOG" | grep -qE '1 passed, 0 failed'; then
        status="PASS"
        note="local worker audio"
      elif tail -40 "$LOG" | grep -qi 'never detected caller'; then
        status="BLOCKED"
        note="local audio STT blocked"
      fi
    fi
  elif [[ "$status" != "PASS" && "$HOSTED_ONLY" == "1" ]]; then
    echo "HOSTED_ONLY=1: no local worker fallback" | tee -a "$LOG"
  fi
  sr=$(grep -oE 'SR[J_][a-zA-Z0-9]+' "$LOG" | tail -1 || true)
  append_row "$seq" "$cid" "$status" "${note}${sr:+; $sr}"
  echo "[$seq $cid] $status — $note $sr" | tee -a "$LOG"
  sleep 3
}

echo "# LiveKit voice sequential $(date -u -Iseconds)" | tee "$LOG"
echo "**Channel:** lk agent simulate audio only" >> "$PROGRESS"
for entry in "${YAMLS[@]}"; do
  IFS='|' read -r seq cid scen <<<"$entry"
  run_one "$seq" "$cid" "$scen"
done
echo "Log: $LOG"