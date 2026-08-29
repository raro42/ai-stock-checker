# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/) — see [RELEASES.md](RELEASES.md).

## [Unreleased]

### Added

### Changed

### Fixed

## [v0.2.2] - 2026-08-29

August paper book paid tuition to breakouts. This release stops confusing activity with edge.

### Added

- Soft relative-strength entry gate (`RS_GATE`) — skip new buys lagging SPY / BTC (~63 sessions); Ops toggle; fail-open.
- Soft scan-breadth entry gate (`BREADTH_GATE`) — skip new buys when scan-list crypto A/D or stock leaders look weak.
- Soft daily loss halt (−2% realized UTC) + single-name concentration cap (30% equity) + pre-trade PASS/WARN/FAIL.
- Post stop-loss buy cooldown (**4h** floor) — blocks revenge refill (CACI→HALO / EOG→EXPE→NTRA).
- Paper calm streak tracker + Ops readout + `scripts/check_promote_compose_ready.py` — ≥30 calm UTC days before compose promote default-on.
- Overweight trim-to-cap — prefer weakest **winner** when available; else worst mark.
- Curated universe refresh + Yahoo movers discovery-only (`yahoo_universe_discovery.py`).
- ATR / R:R risk notes on Screener (`atr_risk.py`) — day-range / vol proxy; **display only**, not live stops.
- Autoresearch idea bank, faster overnight loop (net intervals / sprint / param grid), SPY walk-forward keep gate, idea family tags.
- German Xetra equities with per-symbol session hours; live crypto scan/buys BTC/ETH only.
- Book: buy thesis on fills, sell return %, full fill ledger.
- Ops OpenBB Connections checklist; LaunchAgent overnight loops.

### Changed

- **Stock payoff asymmetry:** take-profit **+8%**, stop **−5%**, rotate only at **≥+5%** (was +5% / −5% / +3%).
- Breakouts need AI **BUY** (not HOLD) + not LOW confidence + pullback ≤ **−2%** from 52w high.
- Overweight books: exits-only until at/under cap (no buys, no scan rotation).
- Anti flip-flop: rebuy cooldown; don’t sell losers to chase scan names.
- Book default max positions **5** / min hold **24h**; Revolut-like fees default.
- Ideas Quiet tips sorted newest-first; GitHub watch tips show last commit date.

### Fixed

- Same-minute refill after stop-loss (process reload + durable cooldown).
- Regime gate ignores NaN closes so SPY does not false risk-off.
- Sub-euro Book fills show five decimals.
- Autoresearch stuck on repeated `sma_exit` churn — diversity rule forces filter ideas.

## [v0.2.1] - 2026-07-26

### Added

- Animated README hero with desk tab tour GIF.

## [v0.2.0] - 2026-07-26

### Added

- First tagged release of the paper desk era.
- Multi-screen desk (Overview / Charts / Screener / Breadth / Book / Ideas / Ops).
- Local D3 charts: unrealized P&L, relative-price hover, since-buy holding paths.
- Scan breadth pulse + daily history; screener counts strip; company names beside tickers.
- Paper desk design skill / editorial desk styling against generic AI-SaaS UI.

### Changed

- Desk auto-refresh slowed to 5 minutes; chart legends and brand chrome tightened.
- Ideas filled with scan candidates, watch status, and shipped transfers.

### Fixed

- Breadth 500 from stale uvicorn after template hot-reload.
- Overlapping relative-price chart legend.

[Unreleased]: https://github.com/raro42/ai-stock-checker/compare/v0.2.2...HEAD
[v0.2.2]: https://github.com/raro42/ai-stock-checker/releases/tag/v0.2.2
[v0.2.1]: https://github.com/raro42/ai-stock-checker/releases/tag/v0.2.1
[v0.2.0]: https://github.com/raro42/ai-stock-checker/releases/tag/v0.2.0
