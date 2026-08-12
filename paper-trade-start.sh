#!/usr/bin/env bash
# Deprecated helper — use docker compose intelligent-trader instead.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "paper-trade-start.sh is deprecated."
echo "Use: docker compose up -d intelligent-trader openbb-backend"
echo "Desk: http://127.0.0.1:7779/desk"
echo "Defaults: €100,000 paper capital via compose · Ops book limits 5 / 24h"
exec docker compose up -d intelligent-trader openbb-backend
