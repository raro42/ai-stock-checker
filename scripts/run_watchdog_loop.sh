#!/usr/bin/env bash
# Run watchdog every 5 minutes; emit AGENT_LOOP_TICK_watchdog when agent fix needed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${WATCHDOG_INTERVAL_SEC:-300}"
cd "$ROOT"
echo "watchdog loop every ${INTERVAL}s"
# First pass immediately
bash "$ROOT/scripts/watchdog.sh" --tick || true
while true; do
  sleep "$INTERVAL"
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) watchdog ==="
  bash "$ROOT/scripts/watchdog.sh" --tick || true
done
