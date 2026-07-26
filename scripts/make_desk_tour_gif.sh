#!/usr/bin/env bash
# Build docs/screenshots/desk-tour.gif from PNGs in docs/screenshots/frames/.
# Capture order: 01-overview … 07-ops (Chrome MCP or browser).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHOT="$ROOT/docs/screenshots"
FRAMES="$SHOT/frames"
NORM="$SHOT/frames_norm"
OUT="$SHOT/desk-tour.gif"

[[ -d "$FRAMES" ]] || { echo "Missing $FRAMES — drop tab PNGs there first."; exit 1; }
shopt -s nullglob
pngs=("$FRAMES"/*.png)
((${#pngs[@]} >= 2)) || { echo "Need ≥2 PNGs in $FRAMES"; exit 1; }

rm -rf "$NORM"
mkdir -p "$NORM"
python3 - <<PY
from pathlib import Path
from PIL import Image

frames = sorted(Path("$FRAMES").glob("*.png"))
imgs = [Image.open(p).convert("RGB") for p in frames]
W = 960
norm = []
for im in imgs:
    h = int(im.height * (W / im.width))
    norm.append(im.resize((W, h), Image.Resampling.LANCZOS))
H = min(im.height for im in norm)
out = Path("$NORM")
for i, im in enumerate(norm, 1):
    im.crop((0, 0, W, H)).save(out / f"{i:02d}.png", optimize=True)
print(f"normalized {len(norm)} → {W}x{H}")
PY

# ~2.2s per tab
ffmpeg -y -framerate 100/220 -i "$NORM/%02d.png" \
  -vf "split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" \
  -loop 0 "$OUT"
ls -lh "$OUT"
echo "Update README hero to docs/screenshots/desk-tour.gif if needed."
