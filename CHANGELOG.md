# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/) — see [RELEASES.md](RELEASES.md).

## [Unreleased]

### Added

- Soft relative-strength entry gate (`RS_GATE`) — skip new buys lagging SPY / BTC (~63 sessions); Ops toggle; fail-open.
- Soft scan-breadth entry gate (`BREADTH_GATE`) — skip new buys when scan-list crypto A/D or stock leaders look weak.
- Paper calm streak tracker + Ops readout + `scripts/check_promote_compose_ready.py` — ≥30 calm UTC days before compose promote default-on.
- Overweight trim-to-cap — sell past-min-hold names (worst mark first) until book ≤ Ops max.
- Curated universe refresh + Yahoo movers discovery-only (`yahoo_universe_discovery.py`, daily stale throttle, `scripts/refresh_stock_universe.py`).
- ATR / R:R risk notes on Screener (`atr_risk.py`) — day-range / vol proxy; **display only**, not live stops.
- Stock-batch A/D on Breadth (this-cycle priced names) alongside crypto leaders pulse.
- Ops OpenBB Connections checklist; `.cursor/mcp.json.example` for Workspace MCP companion.
- GitHub social preview asset (`.github/social-preview.jpg`) — upload still required in repo Settings.
- Champion promote filter (`promote_experiment_strategy`) + live-shaped autoresearch fees.
- Ops book limits (max positions / min hold; default 5 / 24h) and editable AI / fee knobs.
- Revolut-like paper fees default (0.25%/side · €1 min); Ultra / spot presets on Ops.

### Changed

- Overweight books: exits-only until at/under cap (no buys, no scan rotation).
- Anti flip-flop: higher rotate hurdle, rebuy cooldown, don’t sell losers to chase scan names.
- Ideas Quiet tips sorted newest-first; GitHub watch tips show last commit date.
- README documents fee-aware entry gates (regime / RS / breadth / overweight trim).

### Fixed

- Regime gate ignores NaN closes so SPY does not false risk-off.
- Sub-euro Book fills show five decimals.

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

[Unreleased]: https://github.com/raro42/ai-stock-checker/compare/v0.2.1...HEAD
[v0.2.1]: https://github.com/raro42/ai-stock-checker/releases/tag/v0.2.1
[v0.2.0]: https://github.com/raro42/ai-stock-checker/releases/tag/v0.2.0
