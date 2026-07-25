# Improvement Backlog

Living checklist for agents. Work top-down. Check items off when done and verified with tests/docs.

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
- [x] Local Ollama autoresearch worker (`scripts/ollama_autoresearch_worker.py`) to save Cursor tokens

## Next (priority)

- [ ] Complete OpenBB Connections UI bind (allow local network if Test hangs)
- [ ] Optional TradingAgents-style multi-role prompts
- [ ] Benchmark scoring vs buy-and-hold on ETF basket
- [ ] Promote autoresearch champion rules into production defaults after paper month
- [ ] Workspace MCP companion token in Cursor MCP config (user-local)

## Guardrails

- Do not reintroduce sub-hour default hold times.
- Do not add API keys to compose or docs.
- Do not claim Sharpe/win-rate improvements without a backtest artifact.
- Rotate any Finnhub key that was previously committed; use a fresh key in `.env`.
- Commit + push verified work per [GIT.md](GIT.md); never commit `data/`, `.env`, or `autoresearch/results.tsv`.
