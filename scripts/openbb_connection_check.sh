#!/usr/bin/env bash
# Verify OpenBB custom backend is reachable for Connections UI.
set -euo pipefail
BASE="${OPENBB_BACKEND_URL:-http://127.0.0.1:7779}"
fail=0
echo "Checking $BASE ..."
for path in /health /widgets.json /apps.json /; do
  code="$(curl -sS -o /tmp/obb_chk.out -w '%{http_code}' --max-time 5 "$BASE$path" || echo 000)"
  if [[ "$code" == "200" ]]; then
    echo "OK  $code $path"
  else
    echo "FAIL $code $path"
    fail=1
  fi
done
if [[ "$fail" -ne 0 ]]; then
  echo "Start with: docker compose up -d openbb-backend"
  echo "If OpenBB Test hangs: allow local network for https://pro.openbb.co in the browser."
  exit 1
fi
echo "Backend ready. In OpenBB Connections use URL: $BASE"
echo "If Test hangs after this check passes → browser local-network permission (not our API)."
exit 0
