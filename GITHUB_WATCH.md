# GitHub idea watch

Poll curated external repos for **commits and releases**, then surface transferable ideas — never wholesale clones.

## Watchlist

Edit [`config/github_watchlist.json`](config/github_watchlist.json). Current set includes FinRobot, finance-agent-v2, value-investing / portfolio AI agents, and several stock screeners.

## Run

```bash
# one-shot (needs network; uses `gh api` if logged in, else HTTPS + GITHUB_TOKEN)
./scripts/run_github_watch_once.sh

# every 6h (override with GITHUB_WATCH_INTERVAL_SEC)
./scripts/run_github_watch_loop.sh
```

## Outputs

| Path | Purpose |
|------|---------|
| `data/github_watch/state.json` | Last-seen commit SHA / release tag per repo |
| `data/github_watch/latest.md` / `.json` | Latest digest (local; gitignored under `data/`) |
| `docs/history/github_watch_YYYY-MM-DD.md` | Dated archive (commit when useful) |
| `docs/history/github_watch_latest.md` | Latest copy under docs |

When the loop sees **new** activity (not the first baseline), it prints `AGENT_LOOP_TICK_github_watch` for the Cursor agent.

## Rules

1. Steal **one** idea at a time into [IMPROVEMENT.md](IMPROVEMENT.md) Phase C.
2. Re-benchmark / paper-validate before promoting trading logic.
3. Desk UI shows highlights from `data/github_watch/latest.json` when present.
