#!/usr/bin/env bash
# One-shot GitHub idea watch (commits + releases on curated repos).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Prefer project venv-less host Python; script only needs stdlib + optional gh.
exec python3 "$ROOT/scripts/github_idea_watch.py" "$@"
