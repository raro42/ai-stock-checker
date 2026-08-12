# Promote A/B window start — 2026-08-12

Baseline snapshot before fee-adjusted promote-on vs promote-off comparison.
Method: [docs/PROMOTE_AB.md](../PROMOTE_AB.md).

## Knobs (live)

- Book limits: max_positions=5, min_hold=24h (compose aligned)
- Fees: revolut_standard (0.25%/side · €1 min)
- Gates: regime on, RS on, breadth on (pulse fixed 2026-08-12)
- Exits: fixed ±5% via exit_policy (ATR display-only)
- Promote: **on** in trader_config at snapshot time — for A/B, run a promote-**off** control window next, then on

## Book at start

See `data/portfolio.json` / desk Overview at commit time (~€100k paper, fees ~€723, 2–3 holdings).

## Trust questions (C4) — fill when windows complete

1. Ops knobs during each window?
2. Breadth: did stock entries flow after pulse fix?
3. Crypto vs stock PnL share?
4. Still ±5% exits? (yes)

## Verdict

**Pending** — this file only opens the measurement; do not claim promote edge yet.
