#!/usr/bin/env bash
# Access LA (Jenny) — Playwright on FlexAgents "Test Your Agent" (voice/text page).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! python3 -c "import playwright" 2>/dev/null; then
  pip install playwright python-dotenv httpx -q
  playwright install chromium
fi
if ! python3 -c "import httpx" 2>/dev/null; then
  pip install httpx -q
fi

exec python3 eval/platform/run_access_la_dashboard_sequential.py "$@"