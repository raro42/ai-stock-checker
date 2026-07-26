# Documentation maintenance

Keep docs honest for humans and agents. Prefer short truth over marketing.

## Weekly checklist (agents)

1. Diff code vs docs: compose services, CLI flags, AI defaults, ports.
2. Update [README.md](README.md) and [FRIENDS.md](FRIENDS.md) if the happy path changed. Refresh `docs/screenshots/*.jpg` when the desk UI changed (`./scripts/capture_desk_screenshots.sh`).
3. Consider a tagged release per [RELEASES.md](RELEASES.md) if enough user-visible work landed since the last tag.
4. Sync [IMPROVEMENT.md](IMPROVEMENT.md) Done / Next from recent commits.
5. Confirm [OPENBB.md](OPENBB.md), [GIT.md](GIT.md), [AGENTS.md](AGENTS.md) still match reality.
6. Run offline tests: `docker run --rm ai-stock-checker pytest -q`
7. Commit + push per [GIT.md](GIT.md) (never `.env`, never `data/`, never `results.tsv`).

## Script

```bash
./scripts/docs_weekly_check.sh
```

Prints a status report; exit 0 when nothing obvious is stale, non-zero when review is needed.

## Cadence

Weekly agent loop: `AGENT_LOOP_TICK_docs` every 7 days (604800s).
