#!/usr/bin/env bash
# Install a durable SSH tunnel: amvara8 Ollama → local 127.0.0.1:11434.
# For hosts without local Ollama (e.g. amvara3 paper desk).
# Requires: ssh Host "amvara8" that can reach the Ollama box (root SSH config is fine).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_NAME="ai-stock-checker-ollama-amvara8.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
REMOTE_HOST="${OLLAMA_TUNNEL_HOST:-amvara8}"

# Containers reach the host via host-gateway (usually docker0), not 127.0.0.1.
# Binding only the docker bridge keeps Ollama off the public NIC.
if [[ -n "${OLLAMA_TUNNEL_BIND:-}" ]]; then
  LOCAL_BIND="${OLLAMA_TUNNEL_BIND}"
else
  DOCKER_GW="$(ip -4 -o addr show docker0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
  if [[ -z "${DOCKER_GW}" ]]; then
    echo "Could not find docker0 IPv4. Set OLLAMA_TUNNEL_BIND=172.17.0.1:11434 (or your host-gateway)."
    exit 1
  fi
  LOCAL_BIND="${DOCKER_GW}:11434"
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This tunnel installer is for the Linux desk host (amvara3)."
  exit 1
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (needs systemd + ssh to ${REMOTE_HOST})."
  exit 1
fi

SSH_BIN="$(command -v ssh)"
systemctl stop "${UNIT_NAME}" 2>/dev/null || true

cat >"${UNIT_PATH}" <<EOF
[Unit]
Description=AI Stock Checker — tunnel Ollama from ${REMOTE_HOST} to ${LOCAL_BIND}
After=network-online.target docker.service
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

SMOKE_URL="http://${LOCAL_BIND}/api/tags"
echo
echo "Smoke host: curl -sS -m 8 ${SMOKE_URL} | head -c 200"
curl -sS -m 8 "${SMOKE_URL}" | head -c 240 || {
  echo
  echo "Tunnel unit is up but Ollama did not answer yet. Check: journalctl -u ${UNIT_NAME} -n 50"
  exit 1
}
echo
echo
echo "Bind is ${LOCAL_BIND} (docker bridge only — not 0.0.0.0)."
echo "Compose default stays: OLLAMA_HOST=http://host.docker.internal:11434"
echo "Then Ops → ai_mode=validate and restart intelligent-trader."
echo "Repo note: ${ROOT}/docs/history/ollama_amvara8_tunnel_2026-11-18.md"
