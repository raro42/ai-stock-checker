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

# Secrets must not appear in tracked files
if git grep -nE 'FINNHUB_API_KEY=[a-zA-Z0-9]{10,}' -- ':!.env.example' ':!*.md' 2>/dev/null | grep -v '\$\{' | grep -v 'your_' >/dev/null; then
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
