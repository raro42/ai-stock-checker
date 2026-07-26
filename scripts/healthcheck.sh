#!/usr/bin/env bash
# Full stack health for friends / overnight (trader, OpenBB, Ollama, portfolio).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail=0

ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "=== AI Stock Checker health $(date -u +%Y-%m-%dT%H:%MZ) ==="

if docker compose ps --status running -q intelligent-trader 2>/dev/null | grep -q .; then
  ok "intelligent-trader running"
else
  bad "intelligent-trader not running — docker compose up -d intelligent-trader"
fi

if docker compose ps --status running -q openbb-backend 2>/dev/null | grep -q .; then
  ok "openbb-backend running"
else
  bad "openbb-backend not running — docker compose up -d openbb-backend"
fi

if curl -sf --max-time 3 http://127.0.0.1:7779/health >/dev/null; then
  ok "openbb HTTP :7779/health"
else
  bad "openbb HTTP :7779 — ./scripts/openbb_connection_check.sh"
fi

if curl -sf --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
  ok "ollama :11434"
else
  bad "ollama not reachable — ollama serve"
fi

if pgrep -f 'run_ollama_autoresearch_loop.sh' >/dev/null 2>&1; then
  ok "ollama autoresearch loop"
else
  echo "WARN ollama autoresearch loop not running (optional overnight)"
fi

if pgrep -f 'run_watchdog_loop.sh' >/dev/null 2>&1; then
  ok "watchdog loop"
else
  echo "WARN watchdog loop not running (optional overnight)"
fi

if pgrep -f 'run_github_watch_loop.sh' >/dev/null 2>&1; then
  ok "github idea watch loop"
else
  echo "WARN github idea watch loop not running (optional — ./scripts/run_github_watch_loop.sh)"
fi

if [[ -f data/github_watch/latest.json ]]; then
  python3 - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("data/github_watch/latest.json").read_text())
print(f"OK  github_watch repos={d.get('repo_count')} updates={d.get('update_count')} at={d.get('generated_at')}")
PY
fi

if [[ -f data/portfolio.json ]]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = json.loads(Path("data/portfolio.json").read_text())
h = p.get("holdings") or {}
cash = float(p.get("cash") or 0)
fees = float(p.get("total_fees_paid") or 0)
print(f"OK  portfolio cash=€{cash:,.2f} holdings={list(h)} fees=€{fees:,.2f}")
note = p.get("reset_note")
if note:
    print(f"     note: {note}")
PY
else
  bad "data/portfolio.json missing"
fi

if [[ -f data/watchdog/status.txt ]]; then
  echo "--- watchdog status ---"
  cat data/watchdog/status.txt
fi

echo "--- intelligent-trader (last 12 lines) ---"
docker logs --tail 12 intelligent-trader 2>&1 || true

if [[ "$fail" -ne 0 ]]; then
  echo "=== HEALTH FAIL ==="
  exit 1
fi
echo "=== HEALTH OK ==="
exit 0
