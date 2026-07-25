#!/usr/bin/env bash
# Quick health check for intelligent-trader container
set -euo pipefail

NAME="${1:-intelligent-trader}"

if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "FAIL: container '$NAME' is not running"
  echo "Start with: docker compose up -d --build intelligent-trader"
  exit 1
fi

echo "OK: $NAME is running"
echo "--- last 30 log lines ---"
docker logs --tail 30 "$NAME" 2>&1 || true
