#!/usr/bin/env bash
# Run one autoresearch experiment (Docker). Usage from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/autoresearch" "$ROOT/data/experiment_bars"
docker run --rm -e PYTHONPATH=/app -w /app \
  -v "$ROOT/data:/app/data" \
  -v "$ROOT/stock_checker:/app/stock_checker" \
  -v "$ROOT/scripts:/app/scripts" \
  ai-stock-checker \
  python3 scripts/run_experiment.py \
  > "$ROOT/autoresearch/run.log" 2>&1
grep -E '^(val_score|total_return_pct|max_drawdown_pct|sharpe_ratio|total_trades|fees_pct|experiment_seconds|beats_buy_hold_spy_walkforward|spy_wf_blend):' \
  "$ROOT/autoresearch/run.log" || {
  echo "experiment failed; last log lines:" >&2
  tail -n 40 "$ROOT/autoresearch/run.log" >&2
  exit 1
}
