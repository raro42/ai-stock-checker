# Autopilot — continuous improvement (no waiting for prompts)

You are on **full autopilot** for this repo. The human should not need to re-ask for reviews, commits, pushes, restarts, or “what’s next.”

## Mandate

1. Work the **Next** list in [IMPROVEMENT.md](IMPROVEMENT.md) **top-down**, constantly — including while the human sleeps (CEST).
2. After each coherent verified change: **commit + push** per [GIT.md](GIT.md) and `.cursor/rules/commit-push-always.mdc`. Never leave shippable work unpushed overnight — and never leave it uncommitted at end of turn.
3. **Restart as needed**: Docker services (`intelligent-trader`, `openbb-backend`), Ollama autoresearch loop, improve/docs loops — if a process dies, hangs, or code that requires a reload shipped, restart it. Do not wait to be asked. `openbb-backend` runs uvicorn with `--reload` on the mounted package; still run `./scripts/smoke_desk_http.sh` after desk changes.
4. Prefer Docker for tests/runs. Never install on the host. Never commit `.env` / `data/` / `results.tsv`.
5. Do not invent performance claims — require backtest/benchmark artifacts. **Anti-churn packaging ≠ edge.** Offline `val_score` and calm streaks do not prove live expectancy.
6. When a wake loop fires (`AGENT_LOOP_TICK_improve`), **ship at least one idea**: read GitHub watch digests + IMPROVEMENT.md **external review assimilation** section top-down, implement the best small slice, verify, document, commit, push, restart what the change needs — then stop the turn. Do not ask permission.
7. **No new entry gates** until IMPROVEMENT A4–A5 and A14 are addressed (gate thinning / fail-open / regime↔RS overlap).

## Overnight (CEST)

While the human sleeps:

- **Durable keep-alive:** macOS LaunchAgent `com.raro42.ai-stock-checker.overnight-loops` runs `./scripts/ensure_overnight_loops.sh` every **15 minutes** (install: `./scripts/install_overnight_launchagent.sh`). Re-starts dead shell loops after crashes / closed terminals.
- **Limit:** LaunchAgents do **not** fire while the Mac is fully asleep. Leave the machine awake (or power adapter + prevent sleep) for overnight ticks.
- Keep **Ollama autoresearch** looping **night-only** (default 23:00–08:00 in the **machine local** timezone via `ASC_LOCAL_TZ` / `OLLAMA_AUTOSEARCH_TZ` / system; strategy keep/revert + push keeps when `OLLAMA_AUTOSEARCH_PUSH=1`). Process may stay up daytime but must idle.
- Keep **product improve** looping hourly (`./scripts/run_improve_loop.sh`). With `ASC_CURSOR_IMPROVE=1` (LaunchAgent default), each tick runs `cursor agent -p -f` via `./scripts/run_cursor_improve_once.sh` — logs in `data/run_cursor_improve.log`. Ticks are no longer “print only.”
- Keep paper stack up: `docker compose up -d intelligent-trader openbb-backend`.
- Keep **GitHub idea watch** looping (`./scripts/run_github_watch_loop.sh`) so external screener/agent repos surface transferable ideas.
- If git lock / loop crash / container unhealthy → fix and restart; commit+push the fix.
- Morning should show new commits on GitHub and progress in `IMPROVEMENT.md` / `results.tsv`.

### What is durable vs what needs the Mac awake

| Piece | Durable? |
|-------|----------|
| Docker trader / desk | Yes (`restart: unless-stopped`) |
| Shell loops via LaunchAgent ensure | Yes while Mac is awake / logged in |
| Ollama autoresearch worker | Yes if loop process up + night window |
| Cursor improve CLI ticks | Yes if `ASC_CURSOR_IMPROVE=1` + `cursor` on PATH + Mac awake |
| Improve while Mac sleeps | **No** — OS suspends LaunchAgent timers |
## Parallel loops (do not collide)

| Loop | Owner | Cadence | Purpose |
|------|-------|---------|---------|
| Watchdog | `./scripts/run_watchdog_loop.sh` | ~5m | Restart dead containers/loops; wake agent on repeated Tracebacks |
| GitHub idea watch | `./scripts/run_github_watch_loop.sh` | cadence-aware | Commits/releases on curated repos when due → `AGENT_LOOP_TICK_github_watch` |
| Ollama autoresearch | `./scripts/run_ollama_autoresearch_loop.sh` | ~120s **net** only 23:00–08:00 local TZ | Strategy `val_score` keep/revert (no Cursor tokens); day idle |
| Ollama 2h sprint | `./scripts/run_ollama_autoresearch_sprint.sh` | ~45s net for `SPRINT_SEC` (default 2h) | Dense Ollama burst; FORCE=1 by default |
| Param grid (no LLM) | `./scripts/run_param_autoresearch_loop.sh` | ~5s | High-volume knob search; **not** with Ollama loop |
| Product improve | `./scripts/run_improve_loop.sh` → `AGENT_LOOP_TICK_improve` | **1h** | ≥1 idea/tick; always review GitHub watch digest |
| Clean-code agent | `./scripts/run_clean_code_agent.sh` | on improve ticks / manual | Ruff + move ad-hoc slop; gemma4 advisory review |

Never run Cursor `AGENT_LOOP_TICK_autoresearch` alongside the Ollama strategy loop.

**Watchdog vs agent:** shell watchdog auto-restarts infra. Code bugs escalate via `AGENT_LOOP_TICK_watchdog` — then fix, commit, push, restart.

## Roadmap phases

### Phase A — Prove

- [x] Buy-and-hold benchmark vs champion (`scripts/benchmark_buy_hold.py`)
- [x] Persist latest benchmark under `autoresearch/benchmark_latest.txt` (gitignored)
- [x] Live-shaped harness (Revolut fees + book caps) — promote gate must pass **under live fees**
- [x] Promote adapter (`stock_checker/promoted_strategy.py` + Ops `promote_experiment_strategy`) — entry veto only; exits stay in `exit_policy`
- [x] Calm-paper streak tracker (`paper_calm.py`, Ops “Paper calm streak”, `scripts/check_promote_compose_ready.py`) — unlock criterion for compose default
- [x] Compose + trader CLI book limits aligned with Ops DEFAULTS (5 positions / 24h hold) — `tests/test_book_limit_defaults.py`
- [ ] **Promote trust:** fee-adjusted promote-on vs promote-off paper comparison (same book rules). Calm streak ≠ edge. See [docs/PROMOTE_AB.md](docs/PROMOTE_AB.md).
- [ ] Flip `promote_experiment_strategy` **compose default-on** only when calm gate passes **and** promote A/B is documented positive (or explicitly waived by human)
- [x] Hold second overnight loop editing `exit_policy` — deferred by design until the promote compose default is unlocked

### Phase B — Harden paper desk

- [x] OpenBB Connections path: CORS + `openbb_connection_check.sh` + Ops “OpenBB Connections” checklist; browser “allow local network” remains a one-time human click
- [x] Soft-migrate / clearer fee-burn reset path for friends
- [x] Healthcheck + friend onboarding polish

### Phase C — Learn from other agents (research → adopt carefully)

Study (do not wholesale clone) and extract **one** transferable idea at a time, always re-benchmark:

1. **TradingAgents** — multi-role debate prompts for Ollama `validate` mode — done
2. **freqtrade / vectorbt** — walk-forward / hyperopt patterns for harness — WF done
3. **Curated GitHub watch** — screeners + FinRobot / finance agents (`GITHUB_WATCH.md`) — regime + RS + scan-breadth gates shipped
4. **FinRL / OpenTrade** — deferred until Phase A compose promote unlock

### Phase D — Share

- Keep [FRIENDS.md](FRIENDS.md) and README honest — refresh screenshots when the desk UI ships; cut releases per [RELEASES.md](RELEASES.md) (not every commit)
- Public `main` always runnable with Docker + `.env.example`
- [x] Workspace MCP companion — ship [`.cursor/mcp.json.example`](.cursor/mcp.json.example); human pastes token locally (never commit secrets)

## Agent tick checklist

On `AGENT_LOOP_TICK_improve` (hourly):

1. Read IMPROVEMENT.md + AUTOPILOT.md
2. Read `data/github_watch/latest.md` / `docs/history/github_watch_latest.md` — pick ≤1 transferable idea
3. Implement the smallest shippable slice (**at least one** coherent change)
4. Run `./scripts/run_clean_code_agent.sh --apply` when touching messy areas (or once per tick if time)
5. `docker run --rm ai-stock-checker pytest -q -m "not network"` (or compose equivalent)
5b. **Live desk smoke** after any `openbb_backend/` change: `./scripts/smoke_desk_http.sh` (all `/desk/*` must be HTTP 200). Pytest alone is not enough — templates are volume-mounted and can 500 when Python modules are stale.
6. Update IMPROVEMENT.md checkboxes / notes
7. Commit + push (`autoresearch/*` and merge to `main` when product-facing)
8. Restart Docker/loops if the change requires it; confirm they are healthy
9. Short status only — no “should I continue?”
