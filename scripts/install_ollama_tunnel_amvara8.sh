#!/usr/bin/env bash
# Install a durable SSH tunnel: amvara8 Ollama → local 127.0.0.1:11434.
# For hosts without local Ollama (e.g. amvara3 paper desk).
# Requires: ssh Host "amvara8" that can reach the Ollama box (root SSH config is fine).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_NAME="ai-stock-checker-ollama-amvara8.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
REMOTE_HOST="${OLLAMA_TUNNEL_HOST:-amvara8}"
LOCAL_BIND="${OLLAMA_TUNNEL_BIND:-127.0.0.1:11434}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This tunnel installer is for the Linux desk host (amvara3)."
  exit 1
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (needs systemd + ssh to ${REMOTE_HOST})."
  exit 1
fi

SSH_BIN="$(command -v ssh)"
cat >"${UNIT_PATH}" <<EOF
[Unit]
Description=AI Stock Checker — tunnel Ollama from ${REMOTE_HOST} to ${LOCAL_BIND}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${SSH_BIN} -N \\
  -o ExitOnForwardFailure=yes \\
  -o ServerAliveInterval=30 \\
  -o ServerAliveCountMax=3 \\
  -o BatchMode=yes \\
  -L ${LOCAL_BIND}:127.0.0.1:11434 \\
  ${REMOTE_HOST}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"
sleep 1
systemctl --no-pager --full status "${UNIT_NAME}" || true

echo
echo "Smoke: curl -sS -m 5 http://127.0.0.1:11434/api/tags | head -c 200"
curl -sS -m 8 "http://127.0.0.1:11434/api/tags" | head -c 240 || {
  echo
  echo "Tunnel unit is up but Ollama did not answer yet. Check: journalctl -u ${UNIT_NAME} -n 50"
  exit 1
}
echo
echo
echo "Point the desk at the tunnel (already the compose default):"
echo "  OLLAMA_HOST=http://host.docker.internal:11434"
echo "Then Ops → ai_mode=validate (or edit data/trader_config.json) and restart intelligent-trader."
echo "Repo note: ${ROOT}/docs/history/ollama_amvara8_tunnel_2026-11-18.md"
