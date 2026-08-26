# Review — tradermonty/claude-trading-skills CLAUDE.md

**Date:** 2026-08-26  
**Source:** https://github.com/tradermonty/claude-trading-skills/blob/main/CLAUDE.md  
**Verdict:** **Borrow ideas selectively. Do not add the repo or CLAUDE.md wholesale.**

## What it is

A large Claude Code guide for a **public skill marketplace** aimed at equity traders. It documents dozens of skills (screeners, calendars, position sizer, trader memory, Alpaca portfolio manager, edge pipelines, launchd auto-improvers).

It is **not** a drop-in skill for ai-stock-checker. It is maintainer docs for *their* multi-skill product.

## Security / harm review (hard)

| Check | Finding |
|--------|---------|
| Obvious secret exfil in `CLAUDE.md` text | **Not found** in the reviewed file |
| Hardcoded API keys in the doc | **No** — uses env vars; good |
| Encourages keys on CLI (`--api-key`) | **Yes — bad habit.** Process list / shell history leak risk. We must **not** copy that pattern. |
| Live brokerage surface | **Alpaca** paper + live (`ALPACA_PAPER`, Portfolio Manager MCP). High risk if agents treat “production” as “wire live.” |
| Host automation | **launchd** plists for daily skill improvement + weekly/daily skill auto-generation that open PRs. Do **not** install on our Mac. |
| Paid third-party APIs | FMP, FINVIZ Elite — conflicts with our Docker-local, low-cost, no-surprise-deps stance. |
| Trust boundary | Dozens of scripts under `skills/*/scripts/`. `CLAUDE.md` alone is not enough; any borrowed script needs its **own** read before run. |
| Supply chain | Large public repo; `main` can change. Never `curl \| bash` their installers. |

**Bottom line on safety:** The markdown itself does not look like a bomb. Installing their **launchd**, **Alpaca live**, or **unreviewed scripts** *would* expand blast radius (keys, network, git PRs). Treat as research reading only.

## Product fit vs ai-stock-checker

| Their world | Ours |
|-------------|------|
| Many Claude skills + FMP/Finviz/Alpaca | One Docker paper desk + Ollama + local `data/` |
| Human+agent research workflows | Autopilot paper trader with anti-churn rules |
| “Production” skill catalog label | Honest paper marks; no unverified performance claims |
| Auto skill generation / improvement loops | We already have improve + Ollama autoresearch — different goal |

Wholesale add would **fight** our senior-simplify rule (huge CLAUDE.md always-on) and our secrets/deps rules.

## Worth borrowing (ideas only — implement thin, local)

1. **Pre-trade discipline gate** — checklist before new entries (we partly have gates; a desk “why blocked” summary is useful).
2. **Trader memory / postmortem** — thesis → exit → MAE/MFE journal (we now store buy/sell notes; a closed-trade postmortem doc is a natural next IMPROVEMENT item).
3. **Position sizing from stop distance** — we started vol/risk sizing in `entry_guards`; keep it simple.
4. **Drawdown circuit breaker** — soft “halt new buys after N% book DD” (paper only).
5. **Data quality checker** — validate desk/report numbers before claiming results.
6. **Honesty label** — their note that `status: production` ≠ trading correctness matches our “no fabricated Sharpe” rule. Keep that culture.
7. **detect-secrets / no absolute paths hooks** — process hygiene we can mirror if missing.

## Do not borrow / do not install

- Entire skill catalog or their `CLAUDE.md` as always-on agent context  
- FMP / FINVIZ Elite as required deps  
- Alpaca MCP live trading path  
- Their launchd skill-improvement / skill-generation agents  
- `--api-key` on command lines  
- MT5 / futures broker stacks  

## Recommendation

1. **Do not** clone or install `tradermonty/claude-trading-skills` into this project.  
2. **Do** skim for workflow ideas; add **one** IMPROVEMENT checkbox at a time if it fits paper + Docker.  
3. Prefer our rules: senior-simplify, anti-churn, secrets in `.env`, validate before claim.
