# Review — VictorVVedtion/trading-skills (2026-08-26)

**Repo:** https://github.com/VictorVVedtion/trading-skills  
**Stars / activity:** ~16★ · created + last push **2026-04-07** (one-shot publish)  
**License:** MIT  
**Verdict:** **Borrow two tool ideas. Do not install.** Not a “top” by activity; useful as a thin checklist source.

## Security (hard)

| Check | Result |
|--------|--------|
| `curl \| bash` install in README | **Unsafe pattern.** Do not run. Prefer manual read/copy of markdown only. |
| `install.sh` content | Writes only `~/.claude/skills/*/SKILL.md` from this repo’s raw GitHub. **No** `.env` theft, no reverse shell in the reviewed script. Still: never pipe remote bash. |
| Skills content | Markdown personas + checklists. **No** scripts, **no** API keys, **no** network calls. |
| Upsell | Points to [vibe-sensei](https://github.com/VictorVVedtion/vibe-sensei) (full terminal). Treat that as a **separate** review before any install. |

**Not a secret bomb** in the skill markdown. The **install path** is the main footgun.

## What it actually is

- Marketing line “68 legends” = mostly in vibe-sensei. **This repo ships 10 markdown skills** (8 master personas + pre-trade gate + tilt detector).
- Masters (Buffett, Simons, …) are **roleplay prompts** for chat — not executable trading logic for our Docker loop.
- Real substance for us: **Pre-Trade Gate** and **Tilt Detector**.

## Can we borrow ideas? Yes — selectively

### Worth implementing (thin, local, paper)

| Idea | Fit to ai-stock-checker |
|------|-------------------------|
| **9-check pre-trade gate** | We have regime/RS/breadth/earnings/entry_guards. Missing a **single Ops/Book “entry checklist”** that scores PASS/WARN/FAIL (heat, concentration, R:R, stop defined). |
| **Daily loss limit** | Soft halt new buys after N% realized loss **today** (paper). Not in live path yet. |
| **Revenge / same-session refill** | We already pause buys after stop-loss **same cycle**. Extend: after any SL, wait ≥1 full trade interval (or UTC day) before any new equity buy. |
| **Concentration caps** | Soft block if one name would exceed ~25–35% of equity at entry. |
| **Tilt / consecutive losses** | After 2–3 stop-outs in a short window, pause new entries (calm streak already tracks some of this for promote). |

### Do not borrow

| Idea | Why |
|------|-----|
| Master persona skills as always-on agent context | Token bloat; conflicts with senior-simplify; not validated edge |
| Ghost-warning theatrics as product identity | Fun in chat; wrong tone for honest paper desk |
| vibe-sensei live exchange gate | Separate product; needs own security review |
| `curl \| bash` installer | Never |

## Relation to overnight autoresearch

**Autoresearch does *not* focus on “trading skills” (SKILL.md prompts).**

| Loop | What it optimizes |
|------|-------------------|
| **Ollama autoresearch** | `experiment_strategy.py` only → maximize offline `val_score` (walk-forward), keep/revert |
| **Live paper book** | Scanner + `exit_policy` + entry gates (not the champion file unless promote is on) |
| **GitHub Ideas watch** | Transferable **product/UX/risk** patterns → IMPROVEMENT.md one at a time |
| **Cursor improve loop** | Ships desk/ops/code from IMPROVEMENT |

So: skills repos feed **Ideas → IMPROVEMENT**. Autoresearch feeds **strategy coefficients / rules** for optional promote. Different jobs. Both improve the “trading skillset,” but only autoresearch is the overnight **math** loop.

## Watchlist action

Add `VictorVVedtion/trading-skills` for **pre-trade gate / tilt** idea screening (despite low stars / stale push), with explicit “markdown only; no install.sh.”
