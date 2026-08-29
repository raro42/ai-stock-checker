# Paper losing streak analysis — 2026-08-29

**Question:** Why are we losing lately? How do we improve the strategy?

## Snapshot (2026-08-29 ~12:30 UTC)

| Metric | Value |
|--------|--------|
| Marked equity | ~€100.9k (**+0.9%** vs start) |
| Peak (recent) | ~€102.7–102.8k → **~−1.8pp from peak** |
| Fees | **€1,441** (−1.44% of capital) |
| Book | 5/5 · cash ~€71k · JPM, ETH, HALO, SY1.DE, NTRA |
| Unrealized (marks) | ~**−€418** (NTRA −3.9%, ETH −3.1%, HALO −2.2%) |

Still green vs start. The pain is a **drawdown from peak** driven by stops, revenge fills, and forced trims.

## What went wrong (August)

### 1. Fat stops vs thin wins

| Type | Examples | Size |
|------|----------|------|
| Stops (−5–6%) | CACI −€401, EOG −€628, EXPE −€311 | Large |
| “Wins” (+3%) | CBK, DB1, DBK, BTC rotate | Small |

One stop ≈ two rotate wins after fees. Payoff is **skewed against** the book.

### 2. Revenge refill (fixed in code; damage already done)

CACI→HALO, EOG→EXPE, EXPE→**NTRA**. NTRA is now the weakest name (−3.9%), close to stop.

### 3. Overweight trim crystallized −€436 (2026-08-28)

Cutting max 8→5 sold **CBK / MTCH / MMM** at ~−2% each. Correct for size discipline; costly on the mark.

### 4. Live “strategy” ≠ overnight champion

Live book = **scanner breakouts + ±5% exits**. Promote filter is **off**. Autoresearch edits `experiment_strategy.py` only — it does **not** steer live exits. Overnight is stuck on `sma_exit` discards / syntax crashes, so even the offline champion is not improving.

### 5. Fee tax

€1.4k fees on €100k is a hard floor. More churn → harder to stay ahead.

## How to improve (priority)

| # | Change | Why |
|---|--------|-----|
| 1 | **Block stock breakouts with AI LOW confidence** | EXPE/NTRA/MTCH notes were LOW |
| 2 | **Winners-first overweight trim** | Avoid crystallizing −2% names when a winner exists |
| 3 | Keep post-SL cooldown + daily loss halt | Already shipped |
| 4 | Autoresearch: force **filter** ideas when `sma_exit` dominates | Stop spinning on exits |
| 5 | Do **not** flip promote from vibes | Need calm + A/B |
| 6 | Optional later: raise rotate hurdle or trail winners | Asymmetry fix |

## Honest frame

The system is not “broken.” It is running a **breakout scanner with hard stops** in a choppy stretch, while fees and refill chains eat the edge. Fix **entries + trim policy + idea diversity** first; do not loosen stops to hide losses.
