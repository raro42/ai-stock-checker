#!/usr/bin/env bash
# Fresh paper start: archive trades, keep selected holdings, restart trader.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
KEEP="${KEEP_SYMBOLS:-WMT}"
CAPITAL="${RESET_CAPITAL:-100000}"

echo "Stopping intelligent-trader..."
docker compose stop intelligent-trader >/dev/null 2>&1 || true

keep_args=()
# shellcheck disable=SC2206
for s in ${KEEP}; do
  keep_args+=(--keep "$s")
done

python3 "$ROOT/scripts/reset_paper_portfolio.py" --capital "$CAPITAL" "${keep_args[@]}"

echo "Starting intelligent-trader..."
docker compose up -d intelligent-trader

echo "Done. Portfolio:"
python3 -c 'import json;print(json.dumps(json.load(open("data/portfolio.json")),indent=2))'
