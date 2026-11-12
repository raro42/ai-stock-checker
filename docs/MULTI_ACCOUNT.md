# Multi-account paper books — Mode A (GitHub #4)

**Status:** Mode A shipped (2026-11-12) after human signoff on [issue #4](https://github.com/raro42/ai-stock-checker/issues/4).  
Mode B (one trader / `DATA_DIR` per account) stays optional later. Reject Mode C (round-robin).

Signoff: **Mode A** · starting capital **€100 000** · shared zeitfenster book may use named account **`desk`** · max **8** named accounts per host.

Goal: friends compete with separate paper portfolios and see how books evolve, without mixing cash/trades or burning each other’s fee meters.

## Today

| Piece | Path / behavior |
|-------|-----------------|
| Legacy book (default) | `data/portfolio.json` + `data/trades.jsonl` |
| Named books | `data/accounts/<id>/portfolio.json` + `trades.jsonl` |
| Desk switcher | `?account=<id>` on `/desk` (nav preserves query) |
| Leaderboard | Overview strip + `GET /desk/api/leaderboard` + `scripts/paper_leaderboard.py` |
| Shared market state | Scan archives, soft-allow, Yahoo rings, Ops knobs on `DATA_DIR` root |
| Trader | Still one `intelligent-trader` on the shared host book (Mode A) |

`<id>`: lowercase `[a-z][a-z0-9_-]{0,31}` (e.g. `anna`, `ben`, `desk`).

## Scripts

```bash
# Create / reset a named book (€100k default)
python3 scripts/reset_paper_portfolio.py --account anna --capital 100000
python3 scripts/reset_paper_portfolio.py --account desk --capital 100000

# Summarize one book
python3 scripts/summarize_trades.py --account anna

# Offline leaderboard (cost-basis equity · fees shown)
python3 scripts/paper_leaderboard.py
```

Desk: [local](http://127.0.0.1:7779/desk) · [shared](https://stock.zeitfenster.de/desk) — label reads `paper · account anna` / `paper · legacy root`. Leaderboard equity is **cost-basis** until that book is open on the desk with marks.

## What stays shared

- Scan / opportunities archive, breadth pulse, Yahoo fail rings, soft-allow log, chart bars
- Compose anti-churn floors, fee preset default, crypto policy, promote-off Window A protocol
- One `intelligent-trader` process on the host ledger friends choose to autopaper (legacy root or a dedicated mount in Mode B)

## Mode B (optional later)

`ASC_ACCOUNT=anna` + `DATA_DIR=…/accounts/anna` per container. Shared archive must stay on host `data/` so dual traders do not fight pin/heal. Do not start without an explicit follow-up.

## Non-goals (v1)

- Live broker / real money accounts
- Per-account AI models or different fee presets on the shared desk (keeps race fair)
- Auth / passwords (local friends desk; trust the LAN / reverse proxy as today)
- Forced migration of the live zeitfenster root book into `accounts/desk/` — create `desk` with reset when ops wants the named id; legacy root remains the no-query default

## Risks

- Dual traders writing the same archive → pin/heal races. Mitigate: shared archive on host `data/`; account dirs hold **ledger only**.
- Leaderboard equity without marks → cost-basis + `price_coverage: cost` honesty.
- Friends compare gross without fees → leaderboard shows **fees paid**.
