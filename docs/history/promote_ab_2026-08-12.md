# Promote A/B — 2026-08-12

Method: [docs/PROMOTE_AB.md](../PROMOTE_AB.md).

## Knobs (fixed for both windows)

- Book limits: max_positions=5, min_hold=24h
- Fees: revolut_standard (0.25%/side · €1 min)
- Gates: regime on, RS on, breadth on
- Exits: fixed ±5% via exit_policy (ATR display-only)
- AI: validate / gemma4:latest

## Window A — promote **OFF** (control) — STARTED 2026-08-12 ~15:22 UTC

Live `data/trader_config.json` flipped `promote_experiment_strategy=false`.

| Metric | At window start |
|--------|-----------------|
| Cash | €87,790.00 |
| Holdings | JPM, SBUX (cost basis ~€12,665) |
| Fees paid (book life) | €723.48 |
| Trades (book life) | 41 (21 buys / 20 sells) |
| Realized P&L (sells, life) | €1,178.61 |

**Target:** ≥10 trading days (or comparable fill count). Log daily equity / fees / trade count via desk + `scripts/summarize_trades.py`.

Do **not** flip promote back on until Window A completes, then start Window B with the same capital baseline note.

## Window B — promote **ON** — not started

## Trust questions (C4) — fill when windows complete

1. Ops knobs during each window? (same as above unless noted)
2. Breadth: did stock entries flow after pulse fix?
3. Crypto vs stock PnL share?
4. Still ±5% exits? (yes)

## Verdict

**Pending** — control window running; no promote edge claim.
