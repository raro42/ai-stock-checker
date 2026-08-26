#!/usr/bin/env bash
# High-volume param-grid autoresearch (no Ollama). Default interval 5s.
# Do NOT run with the Ollama strategy loop (git race on experiment_strategy.py).
# Night window same as Ollama unless FORCE=1.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INTERVAL="${AUTOSEARCH_PARAM_INTERVAL_SEC:-5}"
export AUTOSEARCH_HOST_SCORE="${AUTOSEARCH_HOST_SCORE:-1}"
export OLLAMA_AUTOSEARCH_PUSH="${OLLAMA_AUTOSEARCH_PUSH:-0}"

in_window() {
  python3 -m stock_checker.autoresearch_schedule in_window
}

seconds_until_open() {
  python3 -m stock_checker.autoresearch_schedule seconds_until_open
}

echo "param autoresearch loop every ${INTERVAL}s (host score=${AUTOSEARCH_HOST_SCORE})"
echo "night window unless OLLAMA_AUTOSEARCH_FORCE=1; stop Ollama autoresearch first"

while true; do
  if [[ "${OLLAMA_AUTOSEARCH_FORCE:-0}" != "1" ]] && [[ "$(in_window)" != "1" ]]; then
    wait_s="$(seconds_until_open)"
    echo "=== $(date -u +%Y-%m-%dT%H:%MZ) outside night window — sleeping ${wait_s}s ==="
    sleep "$wait_s"
    continue
  fi
  start=$(date +%s)
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) param tick ==="
  python3 "$ROOT/scripts/autoresearch_param_worker.py" || true
  elapsed=$(( $(date +%s) - start ))
  remain=$(( INTERVAL - elapsed ))
  if (( remain > 0 )); then
    sleep "$remain"
  fi
done
