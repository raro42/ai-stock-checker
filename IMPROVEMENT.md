# Improvement Backlog

Living checklist for agents. Work top-down. Check items off when done and verified with tests/docs.

**Autopilot:** see [AUTOPILOT.md](AUTOPILOT.md). Do not wait for the human to ask — implement continuously via `AGENT_LOOP_TICK_improve`.

## Done (2026-07-25)

- [x] Remove hardcoded Finnhub key from compose; use `.env` / `.env.example`
- [x] Gitignore `data/`, `.env`, caches
- [x] Anti-churn defaults (4h hold, 15m scan, 5m trade)
- [x] Symbol filters (stables, leveraged, noise)
- [x] Wilder RSI fix
- [x] Real OHLCV backtester (commissions + slippage)
- [x] Offline unit tests (filters, portfolio, RSI, backtester, market hours, archive, AI parse, mtf)
- [x] AGENTS.md + Cursor rule + compose `monitor` profile
- [x] Docs synced to intelligent-trader as primary path
- [x] Offline pytest default (`-m "not network"`)
- [x] Defense-in-depth trade filter in intelligent_trader
- [x] `scripts/summarize_trades.py` for fee vs PnL review
- [x] CLI `backtest` (`sma` + `mtf` strategies)
- [x] Archive retention (7 days)
- [x] Binance min volume $25M
- [x] `scripts/reset_paper_portfolio.py`
- [x] FRIENDS.md one-pager
- [x] Structured AI JSON + reject free-form HOLD fallback
- [x] Finnhub signup note in README
- [x] `scripts/healthcheck.sh`
- [x] `strategy_signals.multi_timeframe_momentum_strategy`
- [x] OpenBB custom backend (`openbb-backend` on :7779) with portfolio/trades/opportunities widgets
- [x] Earnings blackout gate (`earnings_guard.py`) in intelligent trader
- [x] Soft sentiment / near-earnings factor in recommender
- [x] Autoresearch overnight loop (`autoresearch/`, `experiment_strategy.py`)
- [x] Soft fee-burn warning on intelligent trader startup (`fee_burn.py`)
- [x] Weekly docs maintenance (`DOCS_MAINTENANCE.md`, `scripts/docs_weekly_check.sh`)
- [x] Fresh paper reset keeping WMT + committed trade history summary (`docs/history/`, `fresh_start_keep.sh`)
- [x] Morning CEST briefing loop (`AGENT_LOOP_TICK_morning`) for night workshift enhancements
- [x] Clean-code agent (`scripts/clean_code_agent.py`) — ruff F401/F841, move root ad-hoc tests, stale doc redirects, gemma4 review
- [x] Overnight watchdog (`scripts/watchdog.sh` + `run_watchdog_loop.sh`) — restart infra; escalate code bugs via `AGENT_LOOP_TICK_watchdog`
- [x] Local Ollama autoresearch worker (`scripts/ollama_autoresearch_worker.py`) to save Cursor tokens
- [x] README project start date (Oct 2025)
- [x] AUTOPILOT.md continuous-improvement mandate

## Next (priority — autopilot order)

### Phase A — Prove
- [x] Buy-and-hold benchmark script + Docker runner (`scripts/benchmark_buy_hold.py`)
- [x] Record `autoresearch/benchmark_latest.txt` and note verdict in IMPROVEMENT when run
  - **2026-07-25 verdict:** `underperforms_baselines` — strategy val≈6.86 vs SPY B&H≈8.40 (same bars). **Do not promote** champion into live defaults yet; keep Ollama autoresearch + research Phase C.
- [ ] Promote autoresearch champion into production defaults only after beats baselines + paper month

### Phase B — Harden
- [ ] Complete OpenBB Connections UI bind (allow local network if Test hangs)
- [x] Clearer friend fee-burn reset UX (`FRIENDS.md` + reset script discoverability)
- [x] Fix Ollama exp commit messages (no shebang-as-description)

### Phase C — Research other agents (one idea at a time + re-benchmark)
- [ ] TradingAgents-style multi-role prompts for Ollama validate mode
- [ ] Study freqtrade/vectorbt walk-forward patterns; adopt one harness improvement
- [ ] Optional later: FinRL / OpenTrade ideas (only after A–B)

### Phase D — Share
- [ ] Workspace MCP companion token in Cursor MCP config (user-local)
- [ ] Keep FRIENDS/README honest after each promote

## Guardrails

- Do not reintroduce sub-hour default hold times.
- Do not add API keys to compose or docs.
- Do not claim Sharpe/win-rate improvements without a backtest artifact.
- Rotate any Finnhub key that was previously committed; use a fresh key in `.env`.
- Commit + push verified work per [GIT.md](GIT.md); never commit `data/`, `.env`, or `autoresearch/results.tsv`.
- Human should not need to re-prompt for continuous improvement — follow AUTOPILOT.md.
