#!/usr/bin/env bash
# Hourly product improve loop for Cursor agent.
# Emits AGENT_LOOP_TICK_improve — implements ≥1 idea/hour; review GitHub watch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
INTERVAL_SEC="${IMPROVE_INTERVAL_SEC:-3600}"
PROMPT='AUTOPILOT HOURLY IMPROVE. NEVER ask the human. Mandate: implement at least ONE shippable idea this tick. (1) Read AUTOPILOT.md + IMPROVEMENT.md (2) Read data/github_watch/latest.md and docs/history/github_watch_latest.md — steal at most one transferable UX/risk idea from watched repos (xang1234 breadth, screeners, FinRobot, portfolio AI); add IMPROVEMENT checkbox if deferring (3) Ship the highest-value small slice (desk UX, ops honesty, tests, docs) (4) docker pytest offline (5) commit+push per GIT.md; ff-merge product work to main (6) restart services if needed. Short status only.'

echo "improve loop: interval=${INTERVAL_SEC}s cwd=$ROOT"
while true; do
  sleep "$INTERVAL_SEC"
  echo "AGENT_LOOP_TICK_improve $(python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' "$PROMPT")"
done
