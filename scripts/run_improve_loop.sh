#!/usr/bin/env bash
# Hourly product improve loop.
# Always logs AGENT_LOOP_TICK_improve. When ASC_CURSOR_IMPROVE=1, also runs
# scripts/run_cursor_improve_once.sh (Cursor Agent CLI) so ticks are not orphans.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data
INTERVAL_SEC="${IMPROVE_INTERVAL_SEC:-3600}"
# First tick after a short delay so LaunchAgent restarts do not pile agents.
BOOT_SEC="${IMPROVE_BOOT_SEC:-120}"
ASC_CURSOR_IMPROVE="${ASC_CURSOR_IMPROVE:-0}"
PROMPT='AUTOPILOT HOURLY IMPROVE. NEVER ask the human. Mandate: implement at least ONE shippable idea this tick. (1) Read AUTOPILOT.md + IMPROVEMENT.md (2) Read data/github_watch/latest.md and docs/history/github_watch_latest.md — adapt at most one transferable UX/risk pattern from watched repos (xang1234 breadth, screeners, FinRobot, portfolio AI); add IMPROVEMENT checkbox if deferring (3) Ship the highest-value small slice (desk UX, ops honesty, tests, docs) (4) docker pytest offline (5) commit+push per GIT.md; ff-merge product work to main (6) restart services if needed. Short status only.'

echo "$(date -u +%Y-%m-%dT%H:%MZ) improve loop start interval=${INTERVAL_SEC}s boot=${BOOT_SEC}s ASC_CURSOR_IMPROVE=${ASC_CURSOR_IMPROVE} cwd=$ROOT"
sleep "$BOOT_SEC"

while true; do
  TS="$(date -u +%Y-%m-%dT%H:%MZ)"
  echo "$TS AGENT_LOOP_TICK_improve $(python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' "$PROMPT")"
  if [ "$ASC_CURSOR_IMPROVE" = "1" ]; then
    echo "$TS invoking cursor improve once"
    bash "$ROOT/scripts/run_cursor_improve_once.sh" "$PROMPT" || echo "$TS cursor improve failed (see data/run_cursor_improve.log)"
  else
    echo "$TS ASC_CURSOR_IMPROVE=0 — tick logged only (no Cursor CLI)"
  fi
  echo "$TS sleeping ${INTERVAL_SEC}s"
  sleep "$INTERVAL_SEC"
done
