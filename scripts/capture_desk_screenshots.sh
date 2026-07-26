#!/usr/bin/env bash
# Capture paper-desk screenshots for README (JPEG, ≤1280px).
# Requires: desk at DESK_BASE_URL, Chrome/Chromium or macOS screencapture fallback via curl+… 
# Preferred: agent uses Chrome MCP; this script uses a simple HTTP check + reminds.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/screenshots"
BASE="${DESK_BASE_URL:-http://127.0.0.1:7779}"
mkdir -p "$OUT"

echo "Checking desk @ $BASE …"
curl -sf --max-time 10 "$BASE/desk" >/dev/null || {
  echo "Desk not reachable. Start: docker compose up -d openbb-backend"
  exit 1
}

echo "Desk is up."
echo "Capture screenshots with Chrome MCP (or browser) for:"
echo "  $BASE/desk          → 01-overview"
echo "  $BASE/desk/charts   → 02-charts"
echo "  $BASE/desk/book     → 03-book"
echo "  $BASE/desk/breadth  → 04-breadth"
echo "Then compress:"
echo "  cd docs/screenshots && for f in 01-overview 02-charts 03-book 04-breadth; do"
echo "    sips -Z 1280 \"\$f.png\" --out _t.png && sips -s format jpeg -s formatOptions 82 _t.png --out \"\$f.jpg\"; done"

# Optional: if PNGs already dropped in OUT, compress them.
shopt -s nullglob
pngs=("$OUT"/*.png)
if ((${#pngs[@]})); then
  echo "Found PNGs — compressing to JPEG…"
  for png in "${pngs[@]}"; do
    base="$(basename "$png" .png)"
    sips -Z 1280 "$png" --out "$OUT/_tmp.png" >/dev/null
    sips -s format jpeg -s formatOptions 82 "$OUT/_tmp.png" --out "$OUT/${base}.jpg" >/dev/null
    rm -f "$png"
  done
  rm -f "$OUT/_tmp.png"
  ls -lh "$OUT"/*.jpg
fi
