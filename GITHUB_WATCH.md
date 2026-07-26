# GitHub idea watch

Poll curated external repos for **commits and releases**, then surface transferable ideas — never wholesale clones.

## Watchlist

Edit [`config/github_watchlist.json`](config/github_watchlist.json). Current set includes FinRobot, finance-agent-v2, value-investing / portfolio AI agents, and several stock screeners.

## Cadence

Re-checks are **per-repo**, derived from recent commit spacing:

- interval ≈ **½ × average gap** between the last few commits
- clamped to **3h … 7d** (archived → 7d)
- if `pushed_at` is unchanged when a check is due, skip the commits/releases API
- the host loop sleeps until the soonest `next_check_at` (see `data/github_watch/next_sleep_sec`)

Force a full pass: `./scripts/run_github_watch_once.sh --force`

## Run

```bash
# one-shot (needs network; uses `gh api` if logged in, else HTTPS + GITHUB_TOKEN)
./scripts/run_github_watch_once.sh
./scripts/run_github_watch_once.sh --force   # ignore schedule

# adaptive loop (sleeps per cadence, not a fixed 6h)
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

1. Adapt **one** transferable pattern at a time into [IMPROVEMENT.md](IMPROVEMENT.md) Phase C. The hourly improve loop (`scripts/run_improve_loop.sh`) must triage this digest each tick and ship ≥1 idea.
2. Re-benchmark / paper-validate before promoting trading logic.
3. Desk UI shows highlights from `data/github_watch/latest.json` when present.
