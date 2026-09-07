#!/usr/bin/env bash
# One product-improve tick via Cursor Agent CLI (headless).
# Used by run_improve_loop.sh when ASC_CURSOR_IMPROVE=1.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data
LOCKDIR="$ROOT/data/run_cursor_improve.lockdir"
LOG="$ROOT/data/run_cursor_improve.log"
PROMPT="${1:-AUTOPILOT HOURLY IMPROVE. NEVER ask the human. Mandate: implement at least ONE shippable idea this tick. (1) Read AUTOPILOT.md + IMPROVEMENT.md (2) Read data/github_watch/latest.md and docs/history/github_watch_latest.md — adapt at most one transferable UX/risk pattern; add IMPROVEMENT checkbox if deferring (3) Ship the highest-value small slice (desk UX, ops honesty, tests, docs) (4) docker pytest offline (5) commit+push per GIT.md (6) restart services if needed. Short status only.}"

if ! command -v cursor >/dev/null 2>&1; then
  echo "$(date -u +%Y-%m-%dT%H:%MZ) ERROR: cursor CLI not on PATH" | tee -a "$LOG"
  exit 1
fi

acquire_lock() {
  mkdir "$LOCKDIR" 2>/dev/null
}

# Portable lock (macOS has no flock). mkdir is atomic.
if ! acquire_lock; then
  holder=""
  if [ -f "$LOCKDIR/pid" ]; then
    holder="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"
  fi
  if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%MZ) skip: improve already running pid=$holder" | tee -a "$LOG"
    exit 0
  fi
  # Stale lockdir — reclaim.
  rm -rf "$LOCKDIR"
  if ! acquire_lock; then
    echo "$(date -u +%Y-%m-%dT%H:%MZ) skip: improve already running" | tee -a "$LOG"
    exit 0
  fi
fi
echo $$ >"$LOCKDIR/pid"
trap 'rm -rf "$LOCKDIR"' EXIT

# Drop obsolete empty flock file if present.
rm -f "$ROOT/data/run_cursor_improve.lock"

echo "$(date -u +%Y-%m-%dT%H:%MZ) cursor improve start" | tee -a "$LOG"
# -p print mode (non-interactive tools) · -f force allow · sandbox disabled for docker
set +e
cursor agent -p -f --sandbox disabled "$PROMPT" >>"$LOG" 2>&1
rc=$?
set -e
echo "$(date -u +%Y-%m-%dT%H:%MZ) cursor improve end rc=$rc" | tee -a "$LOG"
exit "$rc"
