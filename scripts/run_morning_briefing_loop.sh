#!/usr/bin/env bash
# Wake the agent each morning (CEST ~08:00) with a night-shift briefing prompt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

seconds_until_hour() {
  python3 - <<'PY'
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Berlin")
except Exception:
    tz = None
now = datetime.now(tz) if tz else datetime.now()
target = now.replace(hour=8, minute=0, second=0, microsecond=0)
if now >= target:
    target += timedelta(days=1)
print(int((target - now).total_seconds()))
PY
}

echo "morning briefing loop (CEST 08:00)"
while true; do
  wait_s="$(seconds_until_hour)"
  echo "$(date -u +%Y-%m-%dT%H:%MZ) sleeping ${wait_s}s until next CEST 08:00"
  sleep "$wait_s"
  bash "$ROOT/scripts/morning_briefing.sh" >/tmp/ai_stock_morning_brief.txt 2>&1 || true
  echo "AGENT_LOOP_TICK_morning {\"prompt\":\"MORNING BRIEFING (CEST). NEVER skip. (1) Run ./scripts/morning_briefing.sh if needed (2) Read the latest docs/history/morning_*.md (3) Summarize overnight commits, autoresearch keeps/discards, benchmark verdict, watchdog, portfolio (4) Prompt the human clearly with night workshift enhancements and what to decide today (5) Commit the morning_*.md if new and push (6) Continue autopilot from IMPROVEMENT.md. Do not ask permission to keep working.\"}"
done
