#!/usr/bin/env bash
# Install LaunchAgent: re-ensure overnight loops every 15 minutes + at login.
# Survives terminal close. Does NOT run while the Mac is fully asleep.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.raro42.ai-stock-checker.overnight-loops"
SRC="$ROOT/deploy/launchagents/${LABEL}.plist"
DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data"

python3 - <<PY
from pathlib import Path
home = Path.home()
root = Path("$ROOT")
text = Path("$SRC").read_text()
text = text.replace("/Users/raro42/projects/ai-stock-checker", str(root))
text = text.replace("/Users/raro42", str(home))
Path("$DST").write_text(text)
print(f"wrote {Path('$DST')}")
PY

chmod +x "$ROOT/scripts/ensure_overnight_loops.sh"
chmod +x "$ROOT/scripts/run_cursor_improve_once.sh"
chmod +x "$ROOT/scripts/install_overnight_launchagent.sh"
chmod +x "$ROOT/scripts/run_improve_loop.sh"

# Drop stale nohup loops so new env (ASC_CURSOR_IMPROVE=1) takes effect.
for s in run_watchdog_loop run_github_watch_loop run_improve_loop run_ollama_autoresearch_loop run_morning_briefing_loop; do
  pkill -f "scripts/${s}.sh" 2>/dev/null || true
done
sleep 1

UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/${UID_NUM}" "$DST"
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}"
sleep 2
launchctl print "gui/${UID_NUM}/${LABEL}" 2>&1 | head -30
echo "---"
"$ROOT/scripts/ensure_overnight_loops.sh"
echo "OK: LaunchAgent $LABEL loaded (every 15m + login)"
echo "Note: Mac sleep pauses StartInterval — leave the machine awake overnight for ticks."
echo "Improve: ASC_CURSOR_IMPROVE=1 → hourly cursor agent CLI (see data/run_cursor_improve.log)."
