#!/usr/bin/env bash
# Weekly docs hygiene check — exit 1 if something looks stale.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail=0

echo "=== Docs weekly check $(date -u +%Y-%m-%dT%H:%MZ) ==="

need() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f"
    fail=1
  else
    echo "ok: $f"
  fi
}

need README.md
need FRIENDS.md
need AGENTS.md
need IMPROVEMENT.md
need OPENBB.md
need GIT.md
need DOCS_MAINTENANCE.md
need .env.example
need docker-compose.yml

# Secrets must not appear in tracked compose/source (allow env placeholders)
if git grep -nE 'FINNHUB_API_KEY=[A-Za-z0-9_-]{16,}' -- ':!.env.example' ':!*.md' 2>/dev/null \
  | grep -v 'FINNHUB_API_KEY=\${' \
  | grep -v 'your_' >/dev/null; then
  echo "WARN: possible hardcoded Finnhub key in repo"
  fail=1
else
  echo "ok: no obvious hardcoded Finnhub keys"
fi

# README should mention primary services
for term in intelligent-trader openbb-backend gemma4 FRIENDS.md; do
  if ! grep -q "$term" README.md; then
    echo "STALE README: missing '$term'"
    fail=1
  else
    echo "ok: README mentions $term"
  fi
done

# Compose services exist
if ! grep -q 'intelligent-trader:' docker-compose.yml; then
  echo "STALE: docker-compose missing intelligent-trader"
  fail=1
fi
if ! grep -q 'openbb-backend:' docker-compose.yml; then
  echo "STALE: docker-compose missing openbb-backend"
  fail=1
fi

# FRIENDS clone URL should be real github path when repo exists
if ! grep -q 'github.com/raro42/ai-stock-checker' FRIENDS.md; then
  echo "STALE FRIENDS.md: missing public clone URL"
  fail=1
fi

# Non-history docs must not advertise obsolete entrypoints / toy capital
stale_hits="$(git grep -nE 'enhanced-paper-trader|€10,000|€10000|scan every 5 minutes' -- \
  ':!docs/history/**' ':!CHANGELOG.md' ':!IMPROVEMENT.md' ':!USAGE.md' ':!PAPER_TRADING.md' \
  ':!MONITORING.md' ':!plan.md' ':!ENHANCED_SYSTEM_README.md' ':!scripts/docs_weekly_check.sh' \
  ':!AGENTS.md' 2>/dev/null || true)"
# AGENTS may mention obsolete names only as forbidden examples — checked separately:
if git grep -nE 'enhanced-paper-trader' -- AGENTS.md 2>/dev/null | grep -viE 'not obsolete|forbidden|never|do not|prefer' >/dev/null; then
  echo "STALE AGENTS.md: enhanced-paper-trader mentioned without forbid context"
  fail=1
fi
if [[ -n "$stale_hits" ]]; then
  echo "STALE phrasing in active docs/code:"
  echo "$stale_hits" | head -20
  fail=1
else
  echo "ok: no obsolete entrypoint/capital phrases in active docs"
fi

# Deprecated stubs must point at README
for f in USAGE.md PAPER_TRADING.md MONITORING.md plan.md; do
  if [[ -f "$f" ]] && ! grep -qiE 'Deprecated|see README|FRIENDS' "$f"; then
    echo "STALE: $f should be a short redirect to README/FRIENDS"
    fail=1
  else
    echo "ok: $f is redirect/deprecated stub"
  fi
done

echo "=== building + offline tests ==="
docker build -t ai-stock-checker . >/tmp/docs_weekly_build.log 2>&1
docker run --rm ai-stock-checker pytest -q -m "not network" >/tmp/docs_weekly_pytest.log 2>&1 || {
  echo "FAIL: pytest"
  tail -40 /tmp/docs_weekly_pytest.log
  fail=1
}

if [[ "$fail" -eq 0 ]]; then
  echo "PASS: docs weekly check"
else
  echo "REVIEW NEEDED: docs weekly check found issues"
fi
exit "$fail"
