# Autoresearch — testing ideas (2026-08-26)

**Question:** Should we add more testing on ideas so overnight search finds good things?

**Answer:** Yes — but keep it thin. Autoresearch already *is* an idea tester. Improve **which** ideas run and **what “good” means**.

## What we already test

Each night tick:

1. Propose **one** change to `experiment_strategy.py`
2. Run live-shaped fees + walk-forward folds → `val_score`
3. Keep if score rises; else hard-reset

That is ablation-by-construction (one change). Weak spots: idea source is a short hardcoded string; “good” is only relative to last keep, not vs buy-and-hold; families of failed tweaks repeat.

## What helps (do)

| Upgrade | Why |
|---------|-----|
| Curated **idea bank** | Forces testable knobs (RS, vol, SMA, exits) instead of random jitter |
| Ban recent discards | Already present — keep |
| Keep vs **SPY WF** | A “keep” that loses to buy-and-hold is not promote-ready |
| Idea family ledger | Morning review: “we only tried SMA periods again” |
| Promote A/B on live book | Real test of champion as **entry filter** after fees |

## What does not help (don’t)

- Dumping Buffett/persona skill markdown into autoresearch
- Multi-objective ML search without a single keep metric
- Editing live `exit_policy` in the same loop (deferred until promote unlock)
- More ideas without better **rejection** of weak keeps

## Split of labor (improving the skillset)

| Path | Job |
|------|-----|
| Autoresearch | Offline strategy mutations → better optional promote filter |
| IMPROVEMENT C-* | Desk discipline: daily loss halt, concentration, tilt |
| Promote A/B | Does the champion help the **live paper book**? |

## Shipped this note

- `autoresearch/idea_bank.md` + Ollama worker loads it into the prompt
- IMPROVEMENT: SPY keep-gate + idea ledger still open
