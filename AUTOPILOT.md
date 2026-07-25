# Autopilot — continuous improvement (no waiting for prompts)

You are on **full autopilot** for this repo. The human should not need to re-ask for reviews, commits, pushes, or “what’s next.”

## Mandate

1. Work the **Next** list in [IMPROVEMENT.md](IMPROVEMENT.md) **top-down**, constantly.
2. After each coherent verified change: **commit + push** per [GIT.md](GIT.md).
3. Prefer Docker for tests/runs. Never install on the host. Never commit `.env` / `data/` / `results.tsv`.
4. Do not invent performance claims — require backtest/benchmark artifacts.
5. When a wake loop fires (`AGENT_LOOP_TICK_improve`), implement the top unchecked item (or the next safe slice), verify, document, push — then stop the turn. Do not ask permission.

## Parallel loops (do not collide)

| Loop | Owner | Cadence | Purpose |
|------|-------|---------|---------|
| Ollama autoresearch | `./scripts/run_ollama_autoresearch_loop.sh` | ~8m | Strategy `val_score` keep/revert (no Cursor tokens) |
| Product improve | `AGENT_LOOP_TICK_improve` | ~2h | Code/docs from IMPROVEMENT.md |
| Docs weekly | `AGENT_LOOP_TICK_docs` | 7d | [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) |

Never run Cursor `AGENT_LOOP_TICK_autoresearch` alongside the Ollama strategy loop.

## Roadmap phases

### Phase A — Prove (current)

- [ ] Buy-and-hold benchmark vs champion (`scripts/benchmark_buy_hold.py`)
- [ ] Persist latest benchmark under `autoresearch/benchmark_latest.txt` (gitignored artifact ok)
- [ ] Only promote champion rules into `intelligent_trader` after **beats both baselines** *and* a calm paper month

### Phase B — Harden paper desk

- [ ] OpenBB Connections UI bind (local network)
- [ ] Soft-migrate / clearer fee-burn reset path for friends
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
6. Commit + push both active branches if needed (`autoresearch/*` and merge to `main` when product-facing)
7. Short status only — no “should I continue?”
