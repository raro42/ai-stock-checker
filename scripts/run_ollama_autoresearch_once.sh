#!/usr/bin/env bash
# One Ollama-proposed autoresearch experiment (host Python → Ollama; Docker for backtest).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_AUTOSEARCH_MODEL="${OLLAMA_AUTOSEARCH_MODEL:-gemma4:latest}"
# Push keeps automatically when set (optional)
export OLLAMA_AUTOSEARCH_PUSH="${OLLAMA_AUTOSEARCH_PUSH:-0}"
python3 "$ROOT/scripts/ollama_autoresearch_worker.py" "$@"
