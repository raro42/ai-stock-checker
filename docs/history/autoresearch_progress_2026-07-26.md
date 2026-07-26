# Autoresearch progress — 2026-07-26 late morning

## New walk-forward keep

| | Value |
|--|--------|
| Commit | `36f77df` |
| Idea | Slower exit: require medium SMA decay vs long (not just short &lt; med) |
| WF `val_score` (experiment) | **≈ 6.79** |
| WF blend (benchmark) | **≈ 6.86** |
| Prior WF floor | ≈ 0.82 |

## vs SPY (still the promote gate)

| | WF blend |
|--|----------|
| experiment_strategy | ≈ **6.86** |
| buy_hold_spy | ≈ **7.06** |

**Verdict:** closing the gap fast after the keep-baseline fix, but **still do not promote** (slightly under SPY OOS + need calm paper week/month).

Full-sample remains strong (~15 score, ~+33% ret) — ignore for promote decisions.
