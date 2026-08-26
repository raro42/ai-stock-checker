#!/usr/bin/env bash
# Dense Ollama autoresearch for a fixed wall-clock window (default 2 hours).
# Uses a short interval and net sleep (work time counts toward the interval).
# Daytime OK by default (FORCE=1). Stop Cursor autoresearch first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DURATION_SEC="${OLLAMA_AUTOSEARCH_SPRINT_SEC:-7200}"
INTERVAL="${OLLAMA_AUTOSEARCH_INTERVAL_SEC:-45}"
export OLLAMA_AUTOSEARCH_FORCE="${OLLAMA_AUTOSEARCH_FORCE:-1}"
export OLLAMA_AUTOSEARCH_MODEL="${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest}"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_AUTOSEARCH_PUSH="${OLLAMA_AUTOSEARCH_PUSH:-0}"

END=$(( $(date +%s) + DURATION_SEC ))
echo "ollama autoresearch SPRINT ${DURATION_SEC}s (~$((DURATION_SEC/3600))h) interval=${INTERVAL}s model=${OLLAMA_AUTOSEARCH_MODEL}"
echo "FORCE=${OLLAMA_AUTOSEARCH_FORCE} — stop other autoresearch loops first"

while (( $(date +%s) < END )); do
  start=$(date +%s)
  left=$(( END - start ))
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) sprint tick (remain ${left}s) ==="
  bash "$ROOT/scripts/run_ollama_autoresearch_once.sh" || true
  elapsed=$(( $(date +%s) - start ))
  remain=$(( INTERVAL - elapsed ))
  left=$(( END - $(date +%s) ))
  if (( left < 1 )); then
    break
  fi
  if (( remain > 0 )); then
    sleep_for=$remain
    if (( sleep_for > left )); then
      sleep_for=$left
    fi
    sleep "$sleep_for"
  fi
done
echo "sprint done at $(date -u +%Y-%m-%dT%H:%MZ)"

