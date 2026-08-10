#!/usr/bin/env bash
# Overnight Ollama autoresearch loop — no Cursor tokens.
# Night-only by default: 23:00–08:00 Europe/Berlin (CEST/CET).
# Override window via OLLAMA_AUTOSEARCH_NIGHT_START / _NIGHT_END / _TZ.
# Daytime one-offs: OLLAMA_AUTOSEARCH_FORCE=1.
# Default interval 8 minutes while inside the window. Stop with Ctrl-C or kill $PID.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${OLLAMA_AUTOSEARCH_INTERVAL_SEC:-480}"
cd "$ROOT"

in_window() {
  python3 -m stock_checker.autoresearch_schedule in_window
}

seconds_until_open() {
  python3 -m stock_checker.autoresearch_schedule seconds_until_open
}

echo "ollama autoresearch loop every ${INTERVAL}s (model=${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest})"
echo "night window only (default 23:00-08:00 Europe/Berlin); FORCE=1 to bypass"
echo "Stop Cursor AGENT_LOOP_TICK_autoresearch first to avoid git races."
python3 -m stock_checker.autoresearch_schedule status || true

while true; do
  if [[ "$(in_window)" != "1" ]]; then
    wait_s="$(seconds_until_open)"
    echo "=== $(date -u +%Y-%m-%dT%H:%MZ) outside night window — sleeping ${wait_s}s ==="
    sleep "$wait_s"
    continue
  fi
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) ollama tick ==="
  bash "$ROOT/scripts/run_ollama_autoresearch_once.sh" || true
  sleep "$INTERVAL"
done
