#!/usr/bin/env bash
# Install systemd timer: re-ensure overnight loops every 15 minutes + at boot.
# Survives reboot (system unit). Linux only.
set -euo pipefail
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer is for Linux. On macOS use ./scripts/install_overnight_launchagent.sh"
  exit 1
fi
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Need root to write /etc/systemd/system (sudo $0)"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT="ai-stock-checker-overnight-loops"
SRC_DIR="$ROOT/deploy/systemd"
mkdir -p "$ROOT/data"

python3 - <<PY
from pathlib import Path
root = Path("$ROOT")
home = Path.home()
for name in ("${UNIT}.service", "${UNIT}.timer"):
    text = (Path("$SRC_DIR") / name).read_text()
    text = text.replace("/home/amvara/projects/ai-stock-checker", str(root))
    text = text.replace("HOME=/root", f"HOME={home}")
    # Keep /root/.local/bin; also prepend this user's .local/bin.
    extra = str(home / ".local" / "bin")
    text = text.replace(
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin",
        f"PATH={extra}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin",
    )
    Path(f"/etc/systemd/system/{name}").write_text(text)
    print(f"wrote /etc/systemd/system/{name}")
PY

chmod +x "$ROOT/scripts/ensure_overnight_loops.sh"
chmod +x "$ROOT/scripts/install_overnight_systemd.sh"
chmod +x "$ROOT/scripts/run_cursor_improve_once.sh"
chmod +x "$ROOT/scripts/run_improve_loop.sh"

for s in run_watchdog_loop run_github_watch_loop run_improve_loop run_ollama_autoresearch_loop run_morning_briefing_loop; do
  pkill -f "scripts/${s}.sh" 2>/dev/null || true
done
sleep 1

systemctl daemon-reload
systemctl enable --now "${UNIT}.timer"
systemctl start "${UNIT}.service" || true
sleep 2
systemctl status "${UNIT}.timer" --no-pager || true
echo "---"
"$ROOT/scripts/ensure_overnight_loops.sh"
echo "OK: systemd timer ${UNIT}.timer enabled (every 15m + boot)"
echo "Improve: ASC_CURSOR_IMPROVE=1 → hourly cursor agent CLI (see data/run_cursor_improve.log)."
