# Revolut free-trade allowance — 2026-09-01

## What changed

Paper desk + autoresearch harness now model **Revolut monthly commission-free order legs** (calendar month), then normal per-side fees.

| Preset | Free legs / month | Rate after allowance |
|--------|------------------:|----------------------|
| `revolut_standard` | 1 | 0.25% · €1 min |
| `revolut_plus` | 3 | 0.25% · €1 min |
| `revolut_ultra` | 10 | 0.12% · €1 min |
| `binance_like` | 0 | 0.1% · no floor |

Each **buy or sell** consumes one free leg when allowance remains.

## Ops

- Desk → Ops → **Trading fees** preset (includes free/mo in label).
- Facts row: **Free legs left (YYYY-MM)**.
- Existing books reconcile allowance from trades in the current month on trader restart.

## Notes

- Revolut counts submitted orders per billing cycle; paper uses UTC calendar months.
- Historical `total_fees_paid` is not retroactively reduced — allowance applies to **new** fills only.
- If your plan is Plus (3 free), pick **`revolut_plus`** in Ops.
