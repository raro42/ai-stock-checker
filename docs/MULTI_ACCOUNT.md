# Multi-account paper books — plan (GitHub #4)

**Status:** plan only — **awaiting human signoff** on [issue #4](https://github.com/raro42/ai-stock-checker/issues/4).  
Do **not** implement trader/desk wiring until that signoff lands.

Goal: friends compete with separate paper portfolios and see how books evolve, without mixing cash/trades or burning each other’s fee meters.

## Today (single book)

| Piece | Path / behavior |
|-------|-----------------|
| Portfolio | `data/portfolio.json` |
| Trades | `data/trades.jsonl` |
| Trader + desk | one `DATA_DIR=/data` mount |
| Shared desk | [stock.zeitfenster.de/desk](https://stock.zeitfenster.de/desk) shows **one** book |

Shared scan archives (`data/archive/…`), soft-allow rings, and gate audits are **market state**, not owned by one friend. Only the **ledger** (portfolio + trades + fee allowance) needs per-account isolation for a fair race.

## Proposed shape (smallest honest slice)

### Accounts

- Optional named paper accounts under `data/accounts/<id>/`.
- `<id>`: lowercase `[a-z][a-z0-9_-]{0,31}` (e.g. `anna`, `ben`, `desk`).
- **Default / legacy:** empty id → keep using `data/portfolio.json` + `data/trades.jsonl` unchanged (no migration required for the shared host).
- Each account directory owns at least:
  - `portfolio.json`
  - `trades.jsonl`
  - optional `trader_config.json` **only if** we later allow per-book knobs (v1: **share** Ops knobs; same fees / hold / gates).

### What stays shared

- Scan / opportunities archive, breadth pulse, Yahoo fail rings, soft-allow log, chart bars.
- Compose anti-churn floors, fee preset default, crypto policy, promote-off Window A protocol.
- One `intelligent-trader` process **or** one process per account (see run modes).

### Desk UX (after signoff)

1. **Overview / Book:** account switcher (query `?account=` or Ops select). Default = legacy root book.
2. **Leaderboard strip (read-only):** name · equity · cash · fees paid · open positions · last trade age — from each account’s ledger. No new entry gates.
3. **Honesty:** label clearly `paper · account anna` so nobody confuses shared scan freshness with their own fills.

### Run modes (pick one at signoff)

| Mode | Pros | Cons |
|------|------|------|
| **A — Desk-only ledgers** | Friends reset/fill via scripts; one trader still drives the shared host book | Competition is manual unless each friend self-hosts |
| **B — One trader per account** (`ASC_ACCOUNT=anna` + `DATA_DIR=…/accounts/anna`) | Real independent autopapers | More containers / CPU; must not double-write shared archive |
| **C — One trader, round-robin accounts** | Single process | Complex; easy to cross-contaminate — **reject for v1** |

**Recommendation:** ship **A** first (switcher + leaderboard + reset-per-account script), then optional **B** for friends who want their own autopaper on the same host with isolated `DATA_DIR` mounts. Reject **C**.

### Scripts (after signoff)

```bash
# Create empty €10k book (idempotent)
python3 scripts/reset_paper_portfolio.py --account anna --capital 10000

# Summarize one book
python3 scripts/summarize_trades.py --account anna

# Leaderboard (offline)
python3 scripts/paper_leaderboard.py
```

### Non-goals (v1)

- Live broker / real money accounts
- Per-account AI models or different fee presets on the shared desk (keeps race fair)
- Auth / passwords (local friends desk; trust the LAN / reverse proxy as today)
- Migrating the shared zeitfenster book into `accounts/desk/` unless ops asks

## Risks

- Dual traders writing the same archive → pin/heal races. Mitigate: shared archive stays on host `data/`; account dirs hold **ledger only**.
- Leaderboard equity needs marks → reuse desk mark coverage; show `price coverage` honesty if thin.
- Friends compare gross without fees → leaderboard must show **fees paid** and prefer fee-adjusted net when sells exist.

## Signoff checklist

Human should reply on #4 with:

1. Approve **Mode A** (desk ledgers + leaderboard) ± later **B**, or request changes.
2. Starting capital per account (suggest **€10 000** to match reset docs).
3. Whether the shared zeitfenster desk stays the **legacy root** book or becomes a named `desk` account.
4. Max accounts on one host (suggest **≤8**).

Until then: **no compose / trader / desk code** for multi-account.
