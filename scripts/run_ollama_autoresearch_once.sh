#!/usr/bin/env bash
# One Ollama-proposed autoresearch experiment (host Python → Ollama; Docker for backtest).
# Refuses daytime runs unless OLLAMA_AUTOSEARCH_FORCE=1 (night window: 23:00–08:00 local TZ).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_AUTOSEARCH_MODEL="${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest}"
# Push keeps automatically when set (optional)
export OLLAMA_AUTOSEARCH_PUSH="${OLLAMA_AUTOSEARCH_PUSH:-0}"

if [[ "$(python3 -m stock_checker.autoresearch_schedule in_window)" != "1" ]]; then
  echo "skip: outside autoresearch night window ($(python3 -m stock_checker.autoresearch_schedule status))"
  echo "hint: wait for local 23:00 (see status tz=…), or set OLLAMA_AUTOSEARCH_FORCE=1 for a manual daytime run"
  exit 0
fi

python3 "$ROOT/scripts/ollama_autoresearch_worker.py" "$@"
