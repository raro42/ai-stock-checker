# Improvement Backlog

Living checklist for agents. Work top-down. Check items off when done and verified with tests/docs.

**Autopilot:** see [AUTOPILOT.md](AUTOPILOT.md). Do not wait for the human to ask — implement continuously via `AGENT_LOOP_TICK_improve`.

## Next — external review assimilation (THREE parts; work top-down, miss nothing)

Source reviews (2026-08-12): (A) trading-logic review, (B) maintainability assessment, (C) red-team. Every bullet below maps to at least one finding. Do not skip items because they are “small.”

### A — Trading logic (strategy behavior)

- [x] **A1** One config truth: compose + CLI + `IntelligentTrader` defaults = Ops `max_positions=5` / `min_hold_hours=24` (+ `tests/test_book_limit_defaults.py`)
- [x] **A2** Promote A/B: method + baseline + **Window A (promote off) started** 2026-08-12 — [docs/PROMOTE_AB.md](docs/PROMOTE_AB.md) / [docs/history/promote_ab_2026-08-12.md](docs/history/promote_ab_2026-08-12.md) — Window B + fee-adjusted verdict still pending
- [ ] **A3** Do not flip compose promote default-on until A2 is positive (or human explicitly waives) **and** calm gate passes
- [x] **Crypto live policy (2026-08-14):** BTC/ETH buys only · max 1 crypto slot · crypto TP/SL ±10% (stocks ±5%) — `crypto_policy.py` (PROM/ESP/BANK autopsy; alts remain on scan UI only)
- [x] **A4** Breadth gate honesty: enrich recs with change_24h/pct_from_high; pulse from leaders/breakouts; stock leader detection fixed
- [x] **A5** Fail-open audit: `gate_audit.log_soft_allow` on regime/RS/breadth/promote skip_no_bars
- [x] **A6** Earnings blackout on **rebalance buys** (parity with `execute_new_trades`)
- [x] **A7** Missing `position_entry_times`: do **not** treat as “already past min-hold” (now `hold_seconds = 0`)
- [x] **A8** Wire `flip_flop_blocked_today` into `upsert_calm_day` (rebuy-block counter)
- [x] **A9** Dead `rebalance_threshold`: logged as UNUSED (not consulted by buy/sell)
- [x] **A10** Quarantine non-live ATR/`risk_manager` as display-only (IMPROVEMENT guardrail + README honesty)
- [x] **A11** Score asymmetry: stock score band `40+pct_from_high` + `interleave_asset_slots` for entries
- [x] **A12** Honest product framing: live book = scanner + `exit_policy`; overnight champion = entry filter only — README/PAPER_TRADING/AUTOPILOT
- [x] **A13** Fee model gaps: documented (fees.py + README — allowance/crypto fees not modeled)
- [x] **A14** Regime vs RS overlap: documented in `stock_checker/gate_roles.py` (keep both; prefer RS off first if starved)
- [x] **A15** Min-hold capital trap: Overview stuck line + Ops note
- [x] **A16** Overweight trim crystallizes losses by design — documented in `exit_policy.pick_overweight_trim_candidate` (winners-only trim = future experiment)
- [x] **A17** Fix trader module docstring (“scan every 5 minutes” lie → match compose 15m/5m)
- [x] **A18** Promote contract test: promote on ⇒ entry filter only; SELL does not pass as buy (`test_promote_ignores_champion_sell_for_entry_filter`)
- [x] **A19** Autoresearch universe vs live crypto: noted in PROMOTE_AB / README honesty

### B — Maintainability (ops reliability)

- [x] **B1** Carve `intelligent_trader` god-loop: `entry_gates` / `entry_pipeline` / `trader_cycle` + offline single-cycle fixture (`tests/test_trader_cycle.py`)
- [x] **B2** Overnight loop durability: LaunchAgent `com.raro42.ai-stock-checker.overnight-loops` (15m ensure) + `ASC_CURSOR_IMPROVE=1` → `cursor agent` CLI (`scripts/install_overnight_launchagent.sh`); healthcheck checks LaunchAgent / loops when `REQUIRE_OVERNIGHT_LOOPS=1`
- [x] **B3** Docs diet: redirect/archive `USAGE.md`, `PAPER_TRADING.md`, `MONITORING.md`, `plan.md` → README/FRIENDS
- [x] **B4** Log retention: trader tee rotates at 5MiB (`runtime_log.py`); loop logs under `data/run_*.log` (Ops live tail)
- [x] **B5** Thin tests: entry slots + breadth pulse honesty (`tests/test_entry_slots.py`)
- [x] **B6** Quarantine or delete unused live paths: `paper_trader` vs primary `intelligent_trader` clarity in deprecated PAPER_TRADING + README honesty
- [x] **B7** Reduce AI↔trading path coupling docs: AI validate is optional — README/AGENTS still rules+gates first
- [x] **B8** Extend weekly docs check: forbid stale capital/entrypoint phrases; require deprecated stubs

### C — Red-team (skeptical trust)

- [x] **C1** Gate thinning policy: **no new entry gates** until A4–A5 and A14 addressed (IMPROVEMENT + AUTOPILOT)
- [x] **C2** Success criterion for promote: fee-adjusted live edge vs promote-off control — [docs/PROMOTE_AB.md](docs/PROMOTE_AB.md) (execution = A2)
- [x] **C3** Explicit “anti-loss packaging ≠ edge” in AUTOPILOT mandate
- [x] **C4** Trust questions scaffold in `docs/history/promote_ab_2026-08-12.md` (answers when windows complete)

### Keep (do not regress — strengths from review A)

- No loss-rotation + rotate hurdle ≥3% + rebuy cooldown
- Harsh Revolut-like paper fees as default
- Promote as **entry veto only**
- Overweight → exits-only / no scan-chase buys

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
  - **2026-07-29 live-shaped harness:** Revolut 0.25%+€1 min, max 5 positions, min_hold 1 daily bar. WF blend≈**10.47** vs SPY≈**6.69** → `beats_buy_hold_spy_walkforward: true` (offline only). Pre-live-fee `results.tsv` scores are **not** comparable.
- [x] Live-shaped experiment harness + promote adapter (`promoted_strategy.py`, Ops toggle) — **default off** in code; enable for paper after gate; calm paper month still required before compose default-on
- [x] Calm-paper streak tracker (`paper_calm.py` + Ops + `scripts/check_promote_compose_ready.py`) — ≥30 calm UTC days unlocks compose promote default
- [ ] Flip compose / `DEFAULTS` promote default-on **only** when `./scripts/check_promote_compose_ready.py` exits 0 (currently blocked: book overweight / streak not met)
- [x] Second autoresearch loop mutating `exit_policy` — deferred until compose promote unlock
### Phase B — Harden
- [x] OpenBB connection preflight (`scripts/openbb_connection_check.sh`) + CORS regex + Ops Connections checklist; browser “allow local network” is one human click
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
- [x] Triage GitHub watch → since-buy position charts (one idea)
- [x] Hourly improve loop (`scripts/run_improve_loop.sh`, 1h) — ≥1 idea/tick + GitHub review
- [x] Persist daily scan-pulse rows (`data/scan_breadth_daily.json`) + Breadth “Recent days” (first slice toward multi-day A/D)
- [x] Screener counts strip + weekend-aware empty copy (MonsterDeveloper simplicity)
- [x] Soft SMA market-regime gate for new entries (`market_regime.py` — SPY SMA200 / BTC SMA50; `REGIME_GATE=1`; Ops shows last snap) — RyanJHamby watch idea
- [x] Soft relative-strength entry gate (`relative_strength.py` — stock ≥ SPY / crypto ≥ BTC over 63d; `RS_GATE=1`; Ops toggle; fail-open) — RyanJHamby RS filter
- [x] Soft scan-breadth entry gate (`scan_breadth_gate.py` — crypto A/D + stock leaders on scan list; `BREADTH_GATE=1`) — RyanJHamby breadth idea (scan-list, not full universe)
- [x] Overweight trim-to-cap: sell past-min-hold names until at_cap (`pick_overweight_trim_candidate` loop) — unlocks calm streak without scan-chase rotation
- [x] Curated universe refresh + Yahoo movers discovery-only (`yahoo_universe_discovery.py`, daily stale throttle, `scripts/refresh_stock_universe.py`) — grows scan list, not auto-buy firehose
- [x] ATR / R:R risk notes on Screener (`atr_risk.py` — day-range / vol proxy; display only)
- [x] Broader scan A/D pulse: stock batch up/down this cycle on Breadth + crypto leaders (still not full-universe)
- [x] Ops editable trader knobs (`trader_config.json` + `/desk/api/config`) — AI mode/model, multi-role, regime gate; trader hot-reloads
- [x] Revolut-realistic paper fees (default 0.25%/side · €1 min; Ultra 0.12%; Ops fee preset) — replaces optimistic 0.1%
- [x] Stop loss-rotation: never sell losers to chase new scan names; +5% take-profit; block sub-$1 crypto entries (ESP/BANK autopsy 2026-07-28)
- [x] Ops book limits: max positions + min hold hours (default 5 / 24h) — anti-churn vs Revolut fees; pyramid-up still optional later
- [x] Anti flip-flop: raise rotate hurdle to +3%, rebuy cooldown after exit, only mark stale if off entire scan list + have a replacement (SCHW sell→buy 12m, ~€50 fees)
- [x] Overweight book posture: if holdings > max_positions → TP/SL only (no buys, no scan rotation); AI paper default dialed to validate (less churn than full)
- [x] Scan-list breadth gate shipped (above); stock-batch A/D on Breadth (this-cycle priced names); full-universe A/D still optional later
- [ ] Optional later: FinRL / OpenTrade ideas (only after promote compose unlock)

### Phase D — Share
- [x] Workspace MCP companion example (`.cursor/mcp.json.example`) — human pastes OpenBB token locally
- [x] Keep FRIENDS/README honest after WF re-baseline (no false promote claims)

## Guardrails

- ATR / R:R on Screener is **display-only** (`atr_risk.py`); live exits are fixed ±5% via `exit_policy`, not ATR stops.
- Do not reintroduce sub-hour default hold times.
- Do not add API keys to compose or docs.
- Do not claim Sharpe/win-rate improvements without a backtest artifact.
- **No new entry gates** until IMPROVEMENT A4–A5 and A14 are done.
- Rotate any Finnhub key that was previously committed; use a fresh key in `.env`.
- Commit + push verified work per [GIT.md](GIT.md); never commit `data/`, `.env`, or `autoresearch/results.tsv`.
- Human should not need to re-prompt for continuous improvement — follow AUTOPILOT.md.
