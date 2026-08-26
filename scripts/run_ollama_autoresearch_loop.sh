#!/usr/bin/env bash
# Overnight Ollama autoresearch loop — no Cursor tokens.
# Night-only by default: 23:00–08:00 Europe/Berlin (CEST/CET).
# Override window via OLLAMA_AUTOSEARCH_NIGHT_START / _NIGHT_END / _TZ.
# Daytime one-offs: OLLAMA_AUTOSEARCH_FORCE=1.
# Default interval 8 minutes while inside the window. Stop with Ctrl-C or kill $PID.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Default 120s between tick *starts* (work time counts). Override: OLLAMA_AUTOSEARCH_INTERVAL_SEC.
# Old default was 480s idle *after* each tick — that capped ~60 ideas/night.
INTERVAL="${OLLAMA_AUTOSEARCH_INTERVAL_SEC:-120}"
cd "$ROOT"

in_window() {
  python3 -m stock_checker.autoresearch_schedule in_window
}

seconds_until_open() {
  python3 -m stock_checker.autoresearch_schedule seconds_until_open
}

echo "ollama autoresearch loop every ${INTERVAL}s net (model=${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest})"
echo "night window only (default 23:00-08:00 local TZ; set ASC_LOCAL_TZ / OLLAMA_AUTOSEARCH_TZ); FORCE=1 to bypass"
echo "2h sprint: ./scripts/run_ollama_autoresearch_sprint.sh — dense grid: ./scripts/run_param_autoresearch_loop.sh"
echo "Stop Cursor AGENT_LOOP_TICK_autoresearch first to avoid git races."
python3 -m stock_checker.autoresearch_schedule status || true

while true; do
  if [[ "$(in_window)" != "1" ]]; then
    wait_s="$(seconds_until_open)"
    echo "=== $(date -u +%Y-%m-%dT%H:%MZ) outside night window — sleeping ${wait_s}s ==="
    sleep "$wait_s"
    continue
  fi
  start=$(date +%s)
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) ollama tick ==="
  bash "$ROOT/scripts/run_ollama_autoresearch_once.sh" || true
  elapsed=$(( $(date +%s) - start ))
  remain=$(( INTERVAL - elapsed ))
  if (( remain > 0 )); then
    sleep "$remain"
  fi
done
