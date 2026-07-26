#!/usr/bin/env bash
# Poll curated GitHub repos for new commits/releases.
# Default every 6h. Emits AGENT_LOOP_TICK_github_watch when updates exist.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL="${GITHUB_WATCH_INTERVAL_SEC:-21600}"
cd "$ROOT"
mkdir -p "$ROOT/data/github_watch"
echo "github idea watch loop every ${INTERVAL}s"

run_once() {
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) github_watch ==="
  if ! python3 "$ROOT/scripts/github_idea_watch.py"; then
    echo "WARN github_idea_watch failed" >&2
    return 0
  fi
  local latest="$ROOT/data/github_watch/latest.json"
  if [[ -f "$latest" ]]; then
    local updates
    updates="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("update_count",0))' "$latest")"
    if [[ "${updates}" != "0" ]]; then
      echo "AGENT_LOOP_TICK_github_watch {\"prompt\":\"GitHub idea watch found ${updates} repo(s) with new commits/releases. Read data/github_watch/latest.md (and docs/history/github_watch_latest.md). Pick at most ONE transferable idea that fits our paper desk / screener / risk rules. Add a concrete IMPROVEMENT.md Phase C checkbox if worth doing. Do not clone wholesale. Re-benchmark before adopting trading logic. Commit the dated github_watch_*.md if not already committed, push, continue autopilot.\"}"
    fi
  fi
}

run_once || true
while true; do
  sleep "$INTERVAL"
  run_once || true
done
