#!/usr/bin/env bash
# Live HTTP smoke for the paper desk. Exit 0 only if every route returns 200
# and key payloads include expected fields. Run after desk/backend changes.
set -euo pipefail
BASE="${DESK_BASE_URL:-http://127.0.0.1:7779}"
fail=0

check() {
  local path="$1" expect="${2:-}"
  local code body
  body="$(mktemp)"
  code="$(curl -sS -o "$body" -w "%{http_code}" --max-time 20 "${BASE}${path}" || echo "000")"
  if [[ "$code" != "200" ]]; then
    echo "FAIL ${path} → HTTP ${code}"
    fail=1
  elif [[ -n "$expect" ]] && ! grep -q -- "$expect" "$body"; then
    echo "FAIL ${path} → missing '${expect}'"
    fail=1
  else
    echo "OK   ${path} (${code})"
  fi
  rm -f "$body"
}

echo "smoke desk @ ${BASE}"
check "/health" "" || check "/" ""
check "/desk" "Overview"
check "/desk/charts" "Charts"
check "/desk/screener" "Screener"
check "/desk/breadth" "Scan pulse"
check "/desk/book" "Holdings"
check "/desk/ideas" "Paper candidates"
check "/desk/ops" "ops-ai-mode"
check "/desk/api" "scan_breadth"
check "/desk/api/charts" "from_buy"
check "/desk/api/config" "ai_mode"
check "/desk/static/desk.css" ""
check "/desk/static/charts.js" ""
check "/desk/static/d3.min.js" ""
check "/desk/static/desk.js" "ops-config"

# JSON field presence
api_json="$(mktemp)"
if curl -sf --max-time 20 "${BASE}/desk/api" -o "$api_json" \
  && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert "scan_breadth" in d and "holdings" in d' "$api_json"; then
  echo "OK   /desk/api fields"
else
  echo "FAIL /desk/api missing scan_breadth or holdings"
  fail=1
fi
rm -f "$api_json"

if [[ "$fail" -ne 0 ]]; then
  echo "SMOKE FAILED"
  exit 1
fi
echo "SMOKE PASSED"
