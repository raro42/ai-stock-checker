# Edge fix — payoff + entries (2026-08-29)

**Goal:** Stop bleeding on thin wins / fat stops / frothy breakouts. Not a guarantee of profit.

## Live policy changes

| Knob | Before | After |
|------|--------|--------|
| Stock take-profit | +5% | **+8%** |
| Stock stop | −5% | **−5%** (unchanged) |
| Rotate hurdle | +3% | **+5%** |
| Breakout AI | HOLD/LOW often passed | Needs **BUY** + not LOW |
| Breakout pullback | ≤ −1.5% from high | ≤ **−2.0%** |
| Post-SL buy block | ≥1h | ≥**4h** |

## Why

August math: many exits at ~+3%, stops at −5–6%, then refill into another breakout. That cannot earn after Revolut fees.

## Still true

- Promote filter stays **off** until calm + A/B
- Autoresearch does not own live exits
- No unverified Sharpe/win-rate claims
