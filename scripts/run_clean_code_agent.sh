#!/usr/bin/env bash
# Clean-code agent: review + optional --apply safe fixes (gemma4 advisory on host).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export AI_MODEL="${AI_MODEL:-gemma4:latest}"
export OLLAMA_CLEAN_MODEL="${OLLAMA_CLEAN_MODEL:-gemma4:latest}"
python3 "$ROOT/scripts/clean_code_agent.py" "$@"
