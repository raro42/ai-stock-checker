# Paper book drawdown analysis — 2026-08-28

**Question:** Why does the book feel like it is losing? What can we do better?

## Snapshot (2026-08-28 ~07:30 UTC)

| Metric | Value |
|--------|--------|
| Marked equity | ~€101.3k (**+1.3%** vs €100k start — still green, not a wipeout) |
| Reported return (trader) | ~+1.8% |
| Fees paid | **€1,391** (~1.4% of capital alone) |
| Trades | 77 (42 buys / 35 sells) since 2026-07-26 |
| Realized P&L (sells) | ~€3.2k gross before seeing fee drag on all sides |
| Book | 8/8 full; **7 of 8 red** on mark; only SY1.DE green |

Feeling of “losing” = **recent stop cluster + fee burn + almost all names underwater**, not a total account blow-up.

## What actually hurt (realized)

Stop-like exits (≤ −4.5%):

| When | Symbol | Realized |
|------|--------|----------|
| 2026-07-27 | ESP-USD ×2 | −€870 |
| 2026-07-28 | BANK-USD | −€284 |
| 2026-08-13 | PROM-USD | −€375 |
| 2026-08-24 | **CACI** | **−€401** |
| 2026-08-26 | **EOG** | **−€628** |
| 2026-08-27 | **EXPE** | **−€311** |

Stop cluster sum ≈ **−€2.9k**. Recent equity stops alone ≈ **−€1.3k**.

## Pattern that made it worse: revenge refill

Same-minute refill after stop:

1. CACI SL → **HALO** buy (+4s)
2. EOG SL → **EXPE** buy (+4s)
3. EXPE SL → **NTRA** buy (+3s)

So one stop frees a slot and the scanner immediately loads another breakout. That turns one loss into a **chain**.

Code has `_cycle_had_stop_loss` (same-cycle buy pause). The **running** `intelligent-trader` process started **2026-08-25** and may not have reloaded that logic until restart. Even after reload, “pause this cycle only” is weak: the next 5m tick can refill.

## Structural causes (not one bad symbol)

1. **Payoff asymmetry** — stock stop −5%; many “wins” exit near rotate hurdle **+3%** (DBK/DB1/CBK). One stop ≈ two thin wins after fees.
2. **Fees** — Revolut 0.25%/side · €1 min. €1.4k fees on €100k is the silent tax. More slots = more round-trips.
3. **Ops max_positions = 8** vs product default **5**. Full book = capital stuck in mediocre marks; no cash buffer; every SL opens a refill hunt.
4. **Scanner = breakout near highs** — CACI/EOG/EXPE/NTRA style. AI often says HOLD/LOW; guards help but do not stop all entries.
5. **Promote filter off** — overnight champion does not veto live buys. Autoresearch does not fix the live book until A/B + calm gate.
6. **No daily loss halt / long post-SL cooldown** — IMPROVEMENT `C-dd` / `C-tilt` still open.

## What not to do

- Do not flip promote on from vibes (A3 / calm gate).
- Do not loosen stops to “avoid realizing loss” without a tested rule.
- Do not run param+Ollama autoresearch together.
- Do not treat offline `val_score` as live proof.

## What to do better (priority)

| # | Action | Why |
|---|--------|-----|
| 1 | **Restart trader** so same-cycle SL pause is live | Code on disk ≠ process memory |
| 2 | **Extend post-SL cooldown** (`C-tilt`) — block new equity buys ≥1 trade interval (better: hours) | Breaks CACI→HALO / EOG→EXPE→NTRA |
| 3 | **Cut max_positions 8 → 5** on Ops | Less capital at risk; matches anti-churn docs |
| 4 | Soft **daily loss halt** (`C-dd`) | Stop digging after a bad UTC day |
| 5 | Keep breakout pullback / AI HOLD+LOW guards | Already shipped; do not weaken |
| 6 | Finish promote A/B only when book is calmer | Champion as entry filter, not hope |

## Honest frame

The desk is still **slightly green** vs start, but **fees + stop chains** are eating the edge. Recent weeks feel like losing because **large red days** (EOG, EXPE) dominate memory while thin +3% rotates do not compensate.
