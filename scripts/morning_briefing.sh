#!/usr/bin/env bash
# Build a morning briefing of overnight work (CEST). Writes docs/history/morning_YYYY-MM-DD.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DAY="$(TZ=Europe/Berlin date +%Y-%m-%d)"
OUT="$ROOT/docs/history/morning_${DAY}.md"
mkdir -p "$ROOT/docs/history"

SINCE="$(TZ=Europe/Berlin date -v-18H '+%Y-%m-%d %H:%M' 2>/dev/null || TZ=Europe/Berlin date -d '18 hours ago' '+%Y-%m-%d %H:%M')"

{
  echo "# Morning briefing — ${DAY} (CEST)"
  echo
  echo "Night workshift enhancements for review."
  echo
  echo "## Git commits (last ~18h)"
  echo
  echo '```'
  git log --since="$SINCE" --pretty=format:'%h %ad %s' --date=format:'%Y-%m-%d %H:%M' || true
  echo
  echo '```'
  echo
  echo "## Autoresearch keeps / discards"
  echo
  if [[ -f autoresearch/results.tsv ]]; then
    echo '```'
    tail -n 15 autoresearch/results.tsv
    echo '```'
  else
    echo "_No results.tsv yet._"
  fi
  echo
  echo "## Benchmark (if present)"
  echo
  if [[ -f autoresearch/benchmark_latest.txt ]]; then
    echo '```'
    cat autoresearch/benchmark_latest.txt
    echo '```'
  else
    echo "_No benchmark_latest.txt._"
  fi
  echo
  echo "## Watchdog"
  echo
  if [[ -f data/watchdog/status.txt ]]; then
    echo '```'
    cat data/watchdog/status.txt
    echo '```'
  else
    echo "_No watchdog status._"
  fi
  echo
  echo "## Paper book"
  echo
  if [[ -f data/portfolio.json ]]; then
    echo '```json'
    cat data/portfolio.json
    echo '```'
  fi
  echo
  echo "## Suggested focus today"
  echo
  echo "- Read IMPROVEMENT.md Next items"
  echo "- Only promote strategies that beat buy-and-hold"
  echo "- Check intelligent-trader logs if watchdog flagged issues"
  echo
} >"$OUT"

echo "Wrote $OUT"
cat "$OUT"
