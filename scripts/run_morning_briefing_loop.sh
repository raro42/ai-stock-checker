#!/usr/bin/env bash
# Wake the agent each local morning (~08:00 in ASC_LOCAL_TZ / system TZ).
# Fires at most once per calendar day (no sleep-0 spin).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STAMP_FILE="$ROOT/data/watchdog/last_morning_brief.day"

tz_name() {
  python3 -c 'from stock_checker.autoresearch_schedule import night_window_bounds; print(night_window_bounds()[2])'
}

echo "morning briefing loop (08:00 local via autoresearch_schedule TZ)"
while true; do
  wait_s="$(python3 -m stock_checker.autoresearch_schedule seconds_until_morning 8)"
  TZ_NAME="$(tz_name)"
  echo "$(date -u +%Y-%m-%dT%H:%MZ) sleeping ${wait_s}s until next 08:00 ${TZ_NAME}"
  sleep "$wait_s"

  day="$(python3 -c 'from stock_checker.autoresearch_schedule import night_window_bounds; from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo(night_window_bounds()[2])).strftime("%Y-%m-%d"))')"
  mkdir -p "$(dirname "$STAMP_FILE")"
  if [[ -f "$STAMP_FILE" ]] && [[ "$(cat "$STAMP_FILE")" == "$day" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%MZ) already briefed for $day — skip duplicate"
    sleep 120
    continue
  fi
  echo "$day" >"$STAMP_FILE"

  bash "$ROOT/scripts/morning_briefing.sh" >/tmp/ai_stock_morning_brief.txt 2>&1 || true
  echo "AGENT_LOOP_TICK_morning {\"prompt\":\"MORNING BRIEFING (local TZ). NEVER skip. (1) Run ./scripts/morning_briefing.sh if needed (2) Read the latest docs/history/morning_*.md (3) Summarize overnight commits, autoresearch keeps/discards, benchmark verdict, watchdog, portfolio (4) Prompt the human clearly with night workshift enhancements and what to decide today (5) Commit the morning_*.md if new and push (6) Continue autopilot from IMPROVEMENT.md. Do not ask permission to keep working.\"}"
done
