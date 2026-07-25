# Autopilot — continuous improvement (no waiting for prompts)

You are on **full autopilot** for this repo. The human should not need to re-ask for reviews, commits, pushes, restarts, or “what’s next.”

## Mandate

1. Work the **Next** list in [IMPROVEMENT.md](IMPROVEMENT.md) **top-down**, constantly — including while the human sleeps (CEST).
2. After each coherent verified change: **commit + push** per [GIT.md](GIT.md). Never leave shippable work unpushed overnight.
3. **Restart as needed**: Docker services (`intelligent-trader`, `openbb-backend`), Ollama autoresearch loop, improve/docs loops — if a process dies, hangs, or code that requires a reload shipped, restart it. Do not wait to be asked.
4. Prefer Docker for tests/runs. Never install on the host. Never commit `.env` / `data/` / `results.tsv`.
5. Do not invent performance claims — require backtest/benchmark artifacts.
6. When a wake loop fires (`AGENT_LOOP_TICK_improve`), implement the top unchecked item (or the next safe slice), verify, document, commit, push, restart what the change needs — then stop the turn. Do not ask permission.

## Overnight (CEST)

While the human sleeps:

- Keep **Ollama autoresearch** looping (strategy keep/revert + push keeps when `OLLAMA_AUTOSEARCH_PUSH=1`).
- Keep **product improve** looping (`AGENT_LOOP_TICK_improve`).
- Keep paper stack up: `docker compose up -d intelligent-trader openbb-backend`.
- Keep **watchdog** looping (`./scripts/run_watchdog_loop.sh`) so dead processes come back without a human.
- If git lock / loop crash / container unhealthy → fix and restart; commit+push the fix.
- Morning should show new commits on GitHub and progress in `IMPROVEMENT.md` / `results.tsv`.

## Parallel loops (do not collide)

| Loop | Owner | Cadence | Purpose |
|------|-------|---------|---------|
| Watchdog | `./scripts/run_watchdog_loop.sh` | ~5m | Restart dead containers/loops; wake agent on repeated Tracebacks |
| Ollama autoresearch | `./scripts/run_ollama_autoresearch_loop.sh` | ~8m | Strategy `val_score` keep/revert (no Cursor tokens) |
| Product improve | `AGENT_LOOP_TICK_improve` | ~2h | Code/docs from IMPROVEMENT.md |
| Docs weekly | `AGENT_LOOP_TICK_docs` | 7d | [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) |

Never run Cursor `AGENT_LOOP_TICK_autoresearch` alongside the Ollama strategy loop.

**Watchdog vs agent:** shell watchdog auto-restarts infra. Code bugs escalate via `AGENT_LOOP_TICK_watchdog` — then fix, commit, push, restart.

## Roadmap phases

### Phase A — Prove

- [x] Buy-and-hold benchmark vs champion (`scripts/benchmark_buy_hold.py`)
- [x] Persist latest benchmark under `autoresearch/benchmark_latest.txt` (gitignored)
- [ ] Only promote champion rules into `intelligent_trader` after **beats both baselines** *and* a calm paper month

### Phase B — Harden paper desk

- [ ] OpenBB Connections UI bind (local network)
- [x] Soft-migrate / clearer fee-burn reset path for friends
- [ ] Healthcheck + friend onboarding polish

### Phase C — Steal ideas from other agents (research → adopt carefully)

Study (do not wholesale clone) and extract **one** transferable idea at a time, always re-benchmark:

1. **TradingAgents** — multi-role debate prompts for Ollama `validate` mode
2. **freqtrade / vectorbt** — walk-forward / hyperopt patterns for harness
3. **FinRL / OpenTrade** — only if Phase A–B are solid; RL is optional later

### Phase D — Share

- Keep [FRIENDS.md](FRIENDS.md) and README honest
- Public `main` always runnable with Docker + `.env.example`

## Agent tick checklist

On `AGENT_LOOP_TICK_improve`:

1. Read IMPROVEMENT.md + AUTOPILOT.md
2. Pick the highest unchecked actionable item
3. Implement the smallest shippable slice
4. `docker run --rm ai-stock-checker pytest -q -m "not network"`
5. Update IMPROVEMENT.md checkboxes / notes
6. Commit + push (`autoresearch/*` and merge to `main` when product-facing)
7. Restart Docker/loops if the change requires it; confirm they are healthy
8. Short status only — no “should I continue?”
