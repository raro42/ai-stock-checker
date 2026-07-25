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

## Next (priority)

- [ ] Optional TradingAgents-style multi-role prompts (fundamental/technical/risk)
- [ ] Benchmark current scoring vs buy-and-hold on a small ETF basket
- [ ] Soft-migrate old paper portfolio: warn if fee-burn rate historically high
- [ ] Consider pandas-ta / vectorbt as optional research extras (Docker only, documented)
- [ ] Add recommender-feature parity strategy (RSI/MACD inputs from bars) for backtests

## Guardrails

- Do not reintroduce sub-hour default hold times.
- Do not add API keys to compose or docs.
- Do not claim Sharpe/win-rate improvements without a backtest artifact.
- Rotate any Finnhub key that was previously committed; use a fresh key in `.env`.
