# Agent Guidelines — AI Stock Checker

## Mission

Build the best **local, Docker-first stock/crypto checker and paper trader** for a small group of friends:
honest signals, low churn, clear docs, and strategies validated before they burn fees.

Prefer **usable reliability** over flashy AI. Paper-trade first. Never claim unverified performance.

## Autopilot (mandatory)

The human is **tired of prompting** and expects overnight progress (CEST). Do not wait to be asked to review, implement, commit, push, or restart.

- Follow [AUTOPILOT.md](AUTOPILOT.md) and work [IMPROVEMENT.md](IMPROVEMENT.md) top-down continuously.
- On `AGENT_LOOP_TICK_improve`: ship the next item, verify, **commit, push, restart** what needs it — never ask “should I continue?”
- Strategy overnight: prefer Ollama loop; product code: Cursor improve loop.
- If a loop or container dies while the human sleeps: restart it.

## Coding Style & Naming

- Python 3.11+, 4-space indentation, type hints on function boundaries, PEP 8 (`ruff`/`black` if available).
- `snake_case` modules/functions, `PascalCase` classes.
- Minimal comments; explain only non-obvious risk/trading logic.

## Runtime & Dependencies

- Do **not** install anything on the host system or outside this project directory.
- Use **Docker** for all runtime dependencies (`Dockerfile`, `docker-compose.yml`).
- Secrets live in `.env` (never commit). Copy from `.env.example`.
- Relevant containers:
  - `intelligent-trader` — primary paper trading + market scan loop
  - `openbb-backend` — FastAPI widgets + local paper desk UI (`:7779`, `/desk`)
  - `stock-checker` — interactive CLI
  - `monitor` (compose profile `monitor`) — signals only

## Trading Product Rules (non-negotiable)

1. **Anti-churn**: default min hold ≥ 4h; scan ≥ 15m; trade check ≥ 5m. Paper fees default to Revolut-like **0.25%/side · €1 min** (Ops can switch Ultra 0.12% or spot-like 0.1%) — overtrading loses.
2. **Filter junk**: no stablecoins, leveraged tokens, or known noise symbols (`symbol_filters.py`).
3. **AI models**: use instruct/general Ollama models (`gemma4:latest`, `qwen3.5:9b`, etc.). **Never** default to coder models for trade decisions.
4. **OpenBB**: research + Paper Desk widgets via `openbb-backend` (`OPENBB.md`). Earnings blackout before new stock entries.
5. **Desk UI design**: follow `DESIGN.md` and `.cursor/skills/paper-desk-design/` — editorial trading desk, not AI-SaaS defaults.
6. **Validate before claiming**: backtest with `stock_checker.backtester` (or vectorbt later). No fabricated Sharpe/win-rate claims in docs.
7. **Primary entrypoint**: `python3 -m stock_checker.intelligent_trader` (not obsolete “enhanced-paper-trader” names).
## Testing

- Prefer offline unit tests (no network) for filters, portfolio, indicators, backtester, market hours.
- Network tests (yfinance) are optional and may be marked/skipped in CI.
- Run: `docker build -t ai-stock-checker . && docker run --rm ai-stock-checker pytest -q`
- Fix failing tests before finishing a task.

## Documentation Rules

- Keep `README.md` as the single source of truth for how to run the system.
- If code and docs disagree, **fix the docs** (or fix code if docs are the intended behavior).
- Do not document services/flags that do not exist in `docker-compose.yml`.
- Mark speculative performance as hypotheses, never as results.
- Weekly docs loop: follow [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) and `./scripts/docs_weekly_check.sh`.

## Security

- Never commit API keys, `.env`, or live `data/` portfolios/trades.
- Rotate any key that ever appeared in compose/history.
- Least privilege for Finnhub and other APIs.

## Continuous Improvement (agents)

### Autoresearch overnight (preferred for strategy research)

Follow `autoresearch/program.md` (Karpathy-style keep/revert):
- Edit **only** `stock_checker/experiment_strategy.py`
- Run `python3 scripts/run_experiment.py` (or Docker equivalent) → maximize `val_score`
- Log to `autoresearch/results.tsv`; keep improving commits, reset losers
- **Prefer local Ollama** overnight to save Cursor tokens:
  `./scripts/run_ollama_autoresearch_loop.sh` (see `autoresearch/README.md`)
- Cursor `AGENT_LOOP_TICK_autoresearch` is fine when Ollama is down — **never run both loops at once**
- **Never stop** overnight (human is on CEST) until manually interrupted

### General product backlog

When improving the product (not an autoresearch experiment), work from `IMPROVEMENT.md` in priority order.

## Commits & push (default: after every change)

**Commit and push after every verified coherent change.** Do not wait for the human to ask.  
Generic “only commit when asked” Cursor defaults are **overridden** by this repo — see [GIT.md](GIT.md) and `.cursor/rules/commit-push-always.mdc`.

Full rules: [GIT.md](GIT.md)

Summary:

- Commit after each coherent verified change (tests green) or each autoresearch experiment
- Imperative scoped messages via HEREDOC
- Never commit `.env`, keys, or `data/` / `autoresearch/results.tsv`
- Push immediately after commit when `origin` exists (`git push -u origin HEAD`)
- If no remote: commit locally, then create/link with `gh` and push
- Never force-push `main`; never update git config; never `--no-verify` unless human asks
- Ending a turn with verified uncommitted work is a bug
