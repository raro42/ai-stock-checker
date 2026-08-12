#!/usr/bin/env bash
# Ensure overnight loops are running (idempotent). Safe to cron every 15m.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data
for s in run_watchdog_loop run_github_watch_loop run_improve_loop run_ollama_autoresearch_loop run_morning_briefing_loop; do
  if pgrep -f "scripts/${s}.sh" >/dev/null 2>&1; then
    echo "ok: $s"
    continue
  fi
  if [ "$s" = "run_ollama_autoresearch_loop" ]; then
    nohup env OLLAMA_AUTOSEARCH_PUSH=1 bash "$ROOT/scripts/${s}.sh" >>"data/${s}.log" 2>&1 &
  else
    nohup bash "$ROOT/scripts/${s}.sh" >>"data/${s}.log" 2>&1 &
  fi
  echo "started: $s pid=$!"
done
