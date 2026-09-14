# Promote A/B — 2026-08-12

Method: [docs/PROMOTE_AB.md](../PROMOTE_AB.md).

## Knobs (fixed for both windows)

- Book limits: max_positions=5, min_hold=24h *(protocol; see Window A end note for live drift)*
- Fees: revolut_standard (0.25%/side · €1 min)
- Gates: regime on, RS on, breadth on
- Exits: stock TP **+8%** / SL **−5%** / rotate ≥**+5%** via `exit_policy` (ATR display-only); crypto ±10% when majors policy applies
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

### Checkpoint 2026-09-09 (calendar only)

- Weekday count since start (Mon–Fri inclusive through 2026-09-09): **≥10** → Window A **duration target met**.
- Desk now shows promote A/B glance on Overview / Ops (`build_promote_ab_glance`) — display only.
- **2026-09-09 improve:** same glance parity on Screener / Ideas / Book / Charts / Breadth / scan-log.
- **Still pending then:** fee-adjusted summarize before starting Window B.

### Checkpoint 2026-09-13 (fee-adjusted Window A summarize)

Command: `python3 scripts/summarize_trades.py --since window-a` (also desk promote A/B glance bit).

| Metric (fills ≥ 2026-08-12 15:22 UTC) | Value |
|--------|-------|
| Fills | **30** (18 buys / 12 sells) |
| Fees in window | **€575.16** |
| Realized P&L (sells) | **€2,788.06** |
| Net after sell fees | **€2,550.94** |
| Wins / losses (sells) | 10 / 2 |
| Legs | stock 21 · crypto 9 (includes pre-majors-only alts e.g. PROM) |
| First / last fill | 2026-08-13 06:24 → 2026-08-25 14:45 |
| Trading days (Mon–Fri through 2026-09-13) | **≥10** (target met) |

**Live book at summarize (not a clean mark-to-market equity path):**

| Metric | Value |
|--------|-------|
| Cash | €51,777.16 |
| Open names | JPM, DB1.DE, DBK.DE, CBK.DE, MMM, EOG, ETH-USD, HALO (**8**) |
| Promote | **off** (protocol OK for Window A) |
| Ops `max_positions` | **8** *(drift vs protocol 5 — overweight; calm streak paused)* |
| Fee preset | revolut_standard |

**Honesty:** Window A duration + fill summarize are done. This is **not** a promote edge claim. Do **not** flip compose promote default-on. Window B (promote on, same fee/book rules) still required for fee-adjusted A/B verdict. Prefer restoring max_positions=5 before B so knobs match the protocol table.

Desk: promote A/B glance now appends `€fees · ±P&L · N fills` from `trades.jsonl` when available (`summarize_window_trades`) — portfolio AI fee vs realized pattern; display only.

### Checkpoint 2026-09-14 (Window B readiness honesty)

Desk promote A/B glance no longer says “ready for B” when Ops book caps drift from the protocol table. It shows `B blocked · max pos N≠5` and/or `N open >5` via `window_b_readiness` / `format_window_b_block_bit` (display only). Restore `max_positions=5` (and trim open book toward 5) before starting Window B. Still not a compose promote unlock.

### Checkpoint 2026-09-14 (Window B knob parity)

Same readiness helper now also blocks on `min_hold_hours≠24` and `fee_preset≠revolut_standard` (`hold …h≠24h` / `fee …≠standard`). Protocol table is max 5 · 24h · revolut_standard — portfolio AI readiness pattern; display only.

### Checkpoint 2026-09-14 (Window B soft-gate parity)

Same readiness helper also blocks when soft entry gates drift off (`regime off≠on` / `RS off≠on` / `breadth off≠on`). Protocol keeps regime·RS·breadth **on** for A and B; only promote flips. RyanJHamby / portfolio AI readiness; display only. Still not a compose promote unlock.

### Checkpoint 2026-09-14 (Window B AI-mode parity)

Same readiness helper also blocks when Ops `ai_mode` is not **validate** (`AI off≠validate` / `AI full≠validate`). Protocol knobs table is validate / gemma4:latest — mode drift changes churn; instruct model tag is not a blocker. FinRobot / TradingAgents / portfolio AI; display only. Still not a compose promote unlock.

### Checkpoint 2026-09-14 (Window B multi-role parity)

Same readiness helper also blocks when Ops `ai_multi_role` is off (`multi-role off≠on`). Protocol keeps bull·bear·risk multi-role **on** for A and B. FinRobot / TradingAgents / portfolio AI; display only. Still not a compose promote unlock.

### Checkpoint 2026-09-14 (Window B cadence floors)

Same readiness helper also blocks when scan or trade loops sit under anti-churn floors (`scan Nm<15m` / `trade Nm<5m`). Faster loops skew fee burn and A/B fairness. RyanJHamby / MonsterDeveloper schedule honesty + portfolio AI; display only. Still not a compose promote unlock.

## Window B — promote **ON** — not started

## Trust questions (C4) — fill when windows complete

1. Ops knobs during each window? Window A ended with **max_positions=8** (drift from protocol 5); fees/gates/AI as above; promote off.
2. Breadth: did stock entries flow after pulse fix? *(answer in final verdict)*
3. Crypto vs stock PnL share? Window A legs: 9 crypto / 21 stock (not € P&L split yet).
4. Still stock TP+8%/SL−5% (not ATR)? yes

## Verdict

**Pending** — Window A control summarized; Window B not started; no promote edge claim.
