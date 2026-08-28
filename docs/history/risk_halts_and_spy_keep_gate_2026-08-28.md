# Risk halts + autoresearch gates (2026-08-28)

Shipped under autopilot after paper drawdown review.

## Live desk

| Item | Behavior |
|------|----------|
| **C-dd** | Block new buys if UTC-day realized sell P&L ≤ −2% of initial capital |
| **C-conc** | Block a buy whose notional > 30% of marked equity |
| **C-gate** | Each cycle logs PASS/WARN/FAIL (`pretrade_status`) |
| **C-tilt** | ≥1h buy block after stop-loss (already live) |

## Autoresearch

| Item | Behavior |
|------|----------|
| SPY keep gate | Keep only if `val_score` improves **and** `beats_buy_hold_spy_walkforward` |
| Idea family | `results.tsv` 5th column via `idea_family()` |

## Ops note

`max_positions` set to **5** on the live paper config (data). Book may trim overweight toward cap.
