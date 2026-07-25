# Documentation maintenance

Keep docs honest for humans and agents. Prefer short truth over marketing.

## Weekly checklist (agents)

1. Diff code vs docs: compose services, CLI flags, AI defaults, ports.
2. Update [README.md](README.md) and [FRIENDS.md](FRIENDS.md) if the happy path changed.
3. Sync [IMPROVEMENT.md](IMPROVEMENT.md) Done / Next from recent commits.
4. Confirm [OPENBB.md](OPENBB.md), [GIT.md](GIT.md), [AGENTS.md](AGENTS.md) still match reality.
5. Run offline tests: `docker run --rm ai-stock-checker pytest -q`
6. Commit + push per [GIT.md](GIT.md) (never `.env`, never `data/`, never `results.tsv`).

## Script

```bash
./scripts/docs_weekly_check.sh
```

Prints a status report; exit 0 when nothing obvious is stale, non-zero when review is needed.

## Cadence

Weekly agent loop: `AGENT_LOOP_TICK_docs` every 7 days (604800s).
