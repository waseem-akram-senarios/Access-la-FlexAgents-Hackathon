#!/usr/bin/env bash
# Access LA — one voice sim at a time (audio only). Run from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$ROOT/eval/staging"
PROGRESS="$ROOT/eval/reports/access_la_voice_sim_sequential.md"
LOG="$ROOT/eval/reports/access_la_voice_run_$(date -u +%Y%m%dT%H%M%SZ).log"
WORKER="flexagent_staging_worker.py"
mkdir -p "$ROOT/eval/reports"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
cd "$STAGING"

# Seq | Case-ID | yaml under eval/scenarios
TESTS=(
  "4|V-KB|../scenarios/jenny_separate/01_kb.yaml"
  "28|H-GI-SIM-02|../scenarios/jenny_separate/02_directory.yaml"
  "29|H-GI-SIM-03|../scenarios/jenny_separate/03_case_sms.yaml"
  "30|H-GI-SIM-04|../scenarios/jenny_separate/04_case_lookup.yaml"
  "31|H-GI-SIM-05|../scenarios/jenny_separate/05_callback_sms.yaml"
  "32|H-GI-SIM-06|../scenarios/jenny_separate/06_callback_cancel.yaml"
  "33|H-GI-SIM-07|../scenarios/jenny_separate/07_two_jobs.yaml"
  "34|H-GI-SIM-08|../scenarios/jenny_separate/08_complaint_line.yaml"
  "35|H-GI-SIM-09|../scenarios/jenny_separate/09_no_ride_booking.yaml"
  "36|H-GI-SIM-10|../scenarios/jenny_separate/10_caller_says_no.yaml"
)

run_one() {
  local seq="$1" cid="$2" scen="$3"
  echo "======== SEQ $seq $cid ========" | tee -a "$LOG"
  local status="FAIL"
  local note=""
  if lk agent simulate audio --scenarios "$scen" --yes "$WORKER" 2>&1 | tee -a "$LOG"; then
  if tail -50 "$LOG" | grep -qE '[0-9]+ passed, 0 failed|1 passed, 0 failed'; then
      status="PASS"
    elif tail -50 "$LOG" | grep -qi 'never detected caller'; then
      status="BLOCKED"
      note="platform/STT no caller speech"
    else
      status="FAIL"
      note="see log"
    fi
  else
    if tail -50 "$LOG" | grep -qi 'never detected caller'; then
      status="BLOCKED"
      note="platform/STT"
    fi
  fi
  if grep -oE 'SR_[a-zA-Z0-9]+' "$LOG" | tail -1 >/tmp/sr_last.txt 2>/dev/null; then
    note="${note:+$note; }$(cat /tmp/sr_last.txt)"
  fi
  echo "[$seq|$cid] $status $note" | tee -a "$LOG"
  python3 - "$seq" "$cid" "$status" "$note" <<'PY'
import sys
from pathlib import Path
seq, cid, status, note = sys.argv[1:5]
p = Path(sys.argv[0] if False else Path(__file__).resolve().parents[2] / "eval/reports/access_la_voice_sim_sequential.md")
# fixed path
p = Path("/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/access_la_voice_sim_sequential.md")
text = p.read_text(encoding="utf-8")
row = f"| {seq} | {cid} | **{status}** | {note or '—'} |"
if "| — | — | **IN PROGRESS**" in text:
    text = text.replace("| — | — | **IN PROGRESS** | Preflight… |", row)
else:
    text = text.rstrip() + "\n" + row + "\n"
p.write_text(text, encoding="utf-8")
print(f"Updated progress: {seq} {cid} {status}")
PY
}

echo "# Access LA voice run $(date -u -Iseconds)" | tee "$LOG"
for entry in "${TESTS[@]}"; do
  IFS='|' read -r seq cid scen <<<"$entry"
  run_one "$seq" "$cid" "$scen"
  sleep 2
done
echo "Done. Log: $LOG"