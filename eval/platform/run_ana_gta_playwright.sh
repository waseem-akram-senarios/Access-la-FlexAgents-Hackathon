#!/usr/bin/env bash
# Ana — GTA: Playwright smoke on FlexAgents staging (GTA 25 Nov + N-01..N-14).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! python3 -c "import playwright" 2>/dev/null; then
  echo "Installing playwright…" >&2
  pip install playwright python-dotenv -q
  playwright install chromium
fi

exec python3 eval/platform/run_ana_gta_playwright.py "$@"