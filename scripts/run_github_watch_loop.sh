#!/usr/bin/env bash
# Poll curated GitHub repos only when their cadence says they are due.
# Sleep duration comes from data/github_watch/next_sleep_sec (adaptive).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/data/github_watch"
echo "github idea watch loop (cadence-aware)"

run_once() {
  local force_flag="${1:-}"
  echo "=== $(date -u +%Y-%m-%dT%H:%MZ) github_watch ==="
  if ! python3 "$ROOT/scripts/github_idea_watch.py" ${force_flag}; then
    echo "WARN github_idea_watch failed" >&2
    echo 900 >"$ROOT/data/github_watch/next_sleep_sec"
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

sleep_sec() {
  local f="$ROOT/data/github_watch/next_sleep_sec"
  if [[ -f "$f" ]]; then
    local n
    n="$(tr -cd '0-9' <"$f" | head -c 12)"
    if [[ -n "$n" && "$n" -ge 60 ]]; then
      echo "$n"
      return
    fi
  fi
  echo "${GITHUB_WATCH_FALLBACK_SLEEP_SEC:-3600}"
}

# First pass forces a full cadence calibration.
run_once --force || true
while true; do
  s="$(sleep_sec)"
  echo "sleep ${s}s until next due repo"
  sleep "$s"
  run_once || true
done
