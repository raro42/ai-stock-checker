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
2. **Window A (promote off):** ≥10 trading days **and** ≥10 fills **with ≥3 sells** whose newest close is within **5 weekday days** (record days, fills, buy/sell sides, and last-sell age). Day count alone is a thin control sample — desk promote A/B glance shows triple progress `N/10 days` · `N/10 fills` · `N/3 sells` while A runs (`building sample` when fills stay under the floor; `building closes` when fills are ok but sells stay under 3; `sample ready · keep Window A` when fills+closes meet floors but days are still short; `A open-only · 0 sells` when the ledger is all buys; `A thin closes · N sells <3` when day target is met but closes are sparse — one lucky SELL after many buys is not a fair control; RyanJHamby/xang1234 fresh/aging/stale on last SELL — `A fresh closes · last sell Nd` when ≤3 weekday days; `A aging closes · last sell Nd` warns after 3 weekday days; `A stale closes · last sell Nd` blocks when older than 5 weekday days — staskh confirm-against-latest-closed adapted). Warns `A thin · N fills <10 · keep Window A` when days are met but the ledger is short. Warns `A fee drag {mild|heavy|severe|total} · net −€N · fees N×` when closed rounds exist and in-window fees exceed realized sell P&L (portfolio AI fee-burn + xang1234 severity bands: mild &lt;2× · heavy ≥2× · severe ≥5× · total when realized ≤0; prefers fee-adjusted net € + fees÷realized multiple on the status bit) — warn tone only; does **not** block ready for B (fee drag *is* the control measurement). Speaks quiet complement `A fees ok · net +€N · fees N×` when fees ≤ realized on closed rounds; when fees÷realized ≥0.5 (still ≤1×), speaks `A fees thin · net +€N · fees N×` with warn tone (thin edge before fee drag; does **not** block ready for B) — portfolio AI fee-burn quiet vs high + xang1234 speak-both-sides severity — display only. An all-buy, sparse-close, or stale-close sample is not ready for B — fee-adjusted edge needs **enough fresh** closed rounds (aging still allows ready-for-B with warn tone). Log daily equity, fees, trade count, crypto vs stock contribution (`scripts/summarize_trades.py --since window-a` + portfolio snapshots). Desk promote A/B glance shows in-window fees / **fee-adjusted net** (realized − all buy+sell fees) when `trades.jsonl` is present — not gross sell P&L alone.
3. **Window B (promote on):** same length, same capital baseline (reset or note starting equity), same fees/gates/AI except promote. Desk promote A/B glance warns `B blocked · …` when live knobs drift from protocol max 5 / 24h hold / `revolut_standard` / regime·RS·breadth on / AI `validate` / multi-role on / scan ≥15m / trade ≥5m (or open count > 5) via `window_b_readiness` — restore knobs before starting B. Do not start B while Window A is still `A thin`, `A open-only`, `A thin closes`, `A stale closes`, `building sample`, or `building closes`.
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
