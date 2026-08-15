#!/usr/bin/env bash
# One product-improve tick via Cursor Agent CLI (headless).
# Used by run_improve_loop.sh when ASC_CURSOR_IMPROVE=1.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data
LOCK="$ROOT/data/run_cursor_improve.lock"
LOG="$ROOT/data/run_cursor_improve.log"
PROMPT="${1:-AUTOPILOT HOURLY IMPROVE. NEVER ask the human. Mandate: implement at least ONE shippable idea this tick. (1) Read AUTOPILOT.md + IMPROVEMENT.md (2) Read data/github_watch/latest.md and docs/history/github_watch_latest.md — adapt at most one transferable UX/risk pattern; add IMPROVEMENT checkbox if deferring (3) Ship the highest-value small slice (desk UX, ops honesty, tests, docs) (4) docker pytest offline (5) commit+push per GIT.md (6) restart services if needed. Short status only.}"

if ! command -v cursor >/dev/null 2>&1; then
  echo "$(date -u +%Y-%m-%dT%H:%MZ) ERROR: cursor CLI not on PATH" | tee -a "$LOG"
  exit 1
fi

# Prevent overlapping improve agents
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -u +%Y-%m-%dT%H:%MZ) skip: improve already running" | tee -a "$LOG"
  exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%MZ) cursor improve start" | tee -a "$LOG"
# -p print mode (non-interactive tools) · -f force allow · sandbox disabled for docker
set +e
cursor agent -p -f --sandbox disabled "$PROMPT" >>"$LOG" 2>&1
rc=$?
set -e
echo "$(date -u +%Y-%m-%dT%H:%MZ) cursor improve end rc=$rc" | tee -a "$LOG"
exit "$rc"
