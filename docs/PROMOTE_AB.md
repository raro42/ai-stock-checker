# Promote A/B — how we measure (not vibes)

**Goal:** Decide whether the overnight champion entry filter (`promote_experiment_strategy`) improves the **live paper book** after Revolut-like fees — not whether calm days elapsed or offline `val_score` looked good.

## What promote does / does not do

| Does | Does not |
|------|----------|
| Optional **entry veto** via `experiment_strategy.generate_signals` BUY | Own live exits (always `exit_policy`) |
| Soft-keep when bars missing (`skip_no_bars`) | Prove crypto edge (harness universe is mostly stocks/ETFs) |
| | Replace scanner ranking |

## Protocol (minimum)

1. **Fix knobs** — one config: max 5 / 24h hold / fee preset known (Ops + compose aligned).
2. **Window A (promote off):** ≥10 trading days (or ≥N fills — record both). Log daily equity, fees, trade count, crypto vs stock contribution (`scripts/summarize_trades.py` + portfolio snapshots).
3. **Window B (promote on):** same length, same capital baseline (reset or note starting equity), same fees/gates except promote.
4. **Compare fee-adjusted:** Δ equity − Δ fees, trade count, max DD if available. Promote “wins” only if B beats A on fee-adjusted return **and** does not explode trade count.
5. **Artifact:** write `docs/history/promote_ab_YYYY-MM-DD.md` with knobs, dates, numbers, verdict. Link from IMPROVEMENT A2.

## Non-goals

- Calm streak alone
- Offline walk-forward alone
- Adding more gates mid-test

## Trust questions to answer in the artifact

1. Live Ops knobs during A/B?
2. Did breadth block stock entries?
3. Crypto vs stock PnL share?
4. Still using fixed ±5% exits (yes — ATR is display-only)?
