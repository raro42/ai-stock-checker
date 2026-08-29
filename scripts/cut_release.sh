#!/usr/bin/env bash
# Cut an annotated tag + GitHub Release. Usage: ./scripts/cut_release.sh v0.2.0
# Requires CHANGELOG.md to already contain a ## [vX.Y.Z] section (see RELEASES.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VER="${1:-}"
[[ "$VER" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "Usage: $0 vX.Y.Z"
  exit 1
}

git rev-parse --abbrev-ref HEAD | grep -qx main || {
  echo "Switch to main (or merge first). Current: $(git rev-parse --abbrev-ref HEAD)"
  exit 1
}
git diff --quiet && git diff --cached --quiet || {
  echo "Working tree dirty — commit or stash first."
  exit 1
}

# Hard gate: do not ship a tag without a matching changelog section.
if ! grep -qE "^## \[${VER}\]" CHANGELOG.md; then
  echo "CHANGELOG.md missing section: ## [${VER}] - YYYY-MM-DD"
  echo "Update CHANGELOG.md (move Unreleased → ${VER}), commit, then re-run."
  echo "See RELEASES.md."
  exit 1
fi
if ! grep -qE "^\[${VER}\]: https://github.com/raro42/ai-stock-checker/releases/tag/${VER}$" CHANGELOG.md; then
  echo "CHANGELOG.md missing footer link for ${VER}."
  echo "Add: [${VER}]: https://github.com/raro42/ai-stock-checker/releases/tag/${VER}"
  exit 1
fi

PREV="$(git describe --tags --abbrev=0 2>/dev/null || echo "")"
NOTES="$(mktemp)"
{
  echo "## What's new in ${VER}"
  echo
  echo "User-facing history: [CHANGELOG.md](https://github.com/raro42/ai-stock-checker/blob/main/CHANGELOG.md) (**${VER}**)."
  echo
  if [[ -n "$PREV" ]]; then
    echo "Since ${PREV} (commits):"
    echo
    git log --pretty=format:'- %s' "${PREV}..HEAD"
    echo
  else
    echo "First tagged release of the paper desk era."
    echo
    git log --pretty=format:'- %s' -20
    echo
  fi
  echo
  echo "## Run"
  echo
  echo '```bash'
  echo 'docker compose up -d --build intelligent-trader openbb-backend'
  echo 'open http://127.0.0.1:7779/desk'
  echo '```'
  echo
  echo "Screenshots: see README."
} >"$NOTES"

git tag -a "$VER" -m "Release ${VER}"
git push origin "$VER"
gh release create "$VER" --title "$VER" --notes-file "$NOTES"
rm -f "$NOTES"
echo "Released ${VER}: https://github.com/raro42/ai-stock-checker/releases/tag/${VER}"
