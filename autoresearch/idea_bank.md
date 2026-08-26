# Autoresearch idea bank

One clear mutation per overnight tick. The Ollama worker reads this file.
Do **not** dump marketing skill personas here — only testable strategy knobs.

## How to use

- Pick **one** unused line that is not in recent `discard` rows.
- Edit only `stock_checker/experiment_strategy.py`.
- Keep/revert on walk-forward `val_score` (live-shaped fees).

## Entry filters

- Toggle `REQUIRE_REL_STRENGTH` on/off for one run
- Change `RS_LOOKBACK` in {10, 15, 21, 30, 40}
- Tighten/loosen `MAX_RETURN_STDEV` by ~10–20%
- Volume confirmation `MIN_VOLUME_RATIO` in {1.0, 1.2, 1.3, 1.5}
- Require SPY medium SMA rising / disable SPY filter for one run
- RSI entry only when RSI in [35, 65] (or tighten to [40, 60])

## Structure / SMAs

- Short/med/long SMA stack: try (12/30/90), (15/40/100), (20/50/150)
- Entry only when short > med > long (strict stack)
- Exit when short crosses below med (faster) vs med below long (slower)

## Exits / holds

- Asymmetric: faster stop-style exit, slower take-profit hold
- Require med SMA non-decreasing for holds
- Skip new entries when recent true-range% is elevated

## Diversity / anti-stuck

- Combine two near-miss discards that almost kept (one change only)
- If last 5 discards are SMA-period tweaks, force a **filter** idea next
- If last 5 are filter tweaks, force an **exit** idea next

## Out of scope (not this file)

- Live desk gates (daily loss halt, tilt cooldown) → product `IMPROVEMENT` C-*
- Promote A/B on the live paper book → `docs/PROMOTE_AB.md`
- Persona / marketing skill prompts → never
