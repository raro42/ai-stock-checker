#!/usr/bin/env bash
# OS dispatcher: macOS LaunchAgent or Linux systemd timer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "$(uname -s)" in
  Darwin) exec bash "$ROOT/scripts/install_overnight_launchagent.sh" ;;
  Linux) exec bash "$ROOT/scripts/install_overnight_systemd.sh" ;;
  *)
    echo "Unsupported OS $(uname -s)"
    exit 1
    ;;
esac
