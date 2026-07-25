#!/usr/bin/env bash
# Overnight Ollama autoresearch loop — no Cursor tokens.
# Default interval 8 minutes. Stop with Ctrl-C or kill $PID.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${OLLAMA_AUTOSEARCH_INTERVAL_SEC:-480}"
cd "$ROOT"
echo "ollama autoresearch loop every ${INTERVAL}s (model=${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest})"
echo "Stop Cursor AGENT_LOOP_TICK_autoresearch first to avoid git races."
while true; do
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) ollama tick ==="
  bash "$ROOT/scripts/run_ollama_autoresearch_once.sh" || true
  sleep "$INTERVAL"
done
