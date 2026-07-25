#!/usr/bin/env bash
# Compare experiment_strategy vs buy-and-hold (Docker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/autoresearch" "$ROOT/data/experiment_bars"
OUT="$ROOT/autoresearch/benchmark_latest.txt"
docker run --rm -e PYTHONPATH=/app -w /app \
  -v "$ROOT/data:/app/data" \
  -v "$ROOT/stock_checker:/app/stock_checker" \
  -v "$ROOT/scripts:/app/scripts" \
  ai-stock-checker \
  python3 scripts/benchmark_buy_hold.py | tee "$OUT"
