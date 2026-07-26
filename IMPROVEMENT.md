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
- [x] Watchdog: ignore DNS/network traceback storms; trader logs short network errors without chained Tracebacks (`is_transient_network_error`)
- [x] Local Ollama autoresearch worker (`scripts/ollama_autoresearch_worker.py`) to save Cursor tokens
- [x] README project start date (Oct 2025)
- [x] AUTOPILOT.md continuous-improvement mandate

## Next (priority — autopilot order)

### Phase A — Prove
- [x] Buy-and-hold benchmark script + Docker runner (`scripts/benchmark_buy_hold.py`)
- [x] Record `autoresearch/benchmark_latest.txt` and note verdict in IMPROVEMENT when run
  - **2026-07-25 verdict:** `underperforms_baselines` — strategy val≈6.86 vs SPY B&H≈8.40 (same bars).
  - **2026-07-26 WF re-baseline:** strategy WF blend≈0.87 vs SPY WF≈7.06 → do not promote.
  - **2026-07-26 late morning:** new keep `36f77df` (slower med/long exit) WF blend≈**6.86** vs SPY≈**7.06** — gap nearly closed; **still do not promote**. See `docs/history/autoresearch_progress_2026-07-26.md`.
- [ ] Promote autoresearch champion into production defaults only after **WF beats SPY** + calm paper month

### Phase B — Harden
- [x] OpenBB connection preflight (`scripts/openbb_connection_check.sh`) + CORS regex; UI bind still needs human “allow local network” if Test hangs
- [x] Clearer friend fee-burn reset UX (`FRIENDS.md` + reset script discoverability)
- [x] Fix Ollama exp commit messages (no shebang-as-description)
- [x] Full-stack `scripts/healthcheck.sh` (trader, OpenBB, Ollama, loops, portfolio)
- [x] Quiet AI logs by default (`AI_VERBOSE=0` — one-line results, not full prompt dumps)
- [x] Autoresearch: WF-era keep scoring only + diversity prompt (stop comparing to pre-WF ~14 scores / repeated SMA-exit ideas)
- [x] Weekend **crypto-only** trading (stocks still paused Sat/Sun) — crypto is 24/7

### Phase C — Research other agents (one idea at a time + re-benchmark)
- [x] TradingAgents-style multi-role prompts for Ollama validate mode (`ai_multi_role.py`, `AI_MULTI_ROLE=1` default)
- [x] Walk-forward OOS folds in experiment harness (`walk_forward.py`; `val_score` = 0.75·mean + 0.25·min fold)
- [x] Re-baseline under walk-forward + WF-aware buy-and-hold benchmark
- [x] Curated GitHub idea watch (`config/github_watchlist.json`, `scripts/github_idea_watch.py`, 6h loop) — FinRobot, finance-agent-v2, value-investing agent, portfolio AI, stock screeners
- [x] Multi-screen paper desk (Overview / Screener / Breadth / Book / Ideas / Ops) inspired by xang1234/stock-screener page map — local vanilla HTML, favicon, a11y/SEO basics
- [x] D3 charts screen (vendored local d3.min.js) — equity path, allocation donut, relative prices
- [x] Paper Desk design skill + brief (`DESIGN.md`, `.cursor/skills/paper-desk-design`) — anti AI-slop / editorial desk
- [x] Since-buy holding paths (Charts + Book sparklines; portfolio-AI inspiration) — **no forecast lines**
- [x] Scan pulse on Breadth (crypto A/D + ±4% movers + near-highs) — xang1234/StockBee-lite from scan lists
- [x] Restyle desk CSS to match DESIGN.md — `--font-data` on money/%, sharper chart mounts, stronger grain (2026-07-26 improve tick)
- [x] Ops read-only trader config (AI mode / LLM / hold / scan — no secrets) — settings visibility for friends
- [ ] Optional later: FinRL / OpenTrade ideas (only after promote gate is green)
- [x] Triage GitHub watch → since-buy position charts (one idea)
- [x] Hourly improve loop (`scripts/run_improve_loop.sh`, 1h) — ≥1 idea/tick + GitHub review
- [x] Persist daily scan-pulse rows (`data/scan_breadth_daily.json`) + Breadth “Recent days” (first slice toward multi-day A/D)
- [x] Screener counts strip + weekend-aware empty copy (MonsterDeveloper simplicity)
- [x] Soft SMA market-regime gate for new entries (`market_regime.py` — SPY SMA200 / BTC SMA50; `REGIME_GATE=1`; Ops shows last snap) — RyanJHamby watch idea
- [ ] Optional later: full-universe breadth advance/decline series (still needs wider universe stats)

### Phase D — Share
- [ ] Workspace MCP companion token in Cursor MCP config (user-local — needs human token)
- [x] Keep FRIENDS/README honest after WF re-baseline (no false promote claims)

## Guardrails

- Do not reintroduce sub-hour default hold times.
- Do not add API keys to compose or docs.
- Do not claim Sharpe/win-rate improvements without a backtest artifact.
- Rotate any Finnhub key that was previously committed; use a fresh key in `.env`.
- Commit + push verified work per [GIT.md](GIT.md); never commit `data/`, `.env`, or `autoresearch/results.tsv`.
- Human should not need to re-prompt for continuous improvement — follow AUTOPILOT.md.
