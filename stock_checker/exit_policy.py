"""
Exit / rotation policy for the paper desk.

Design intent (learned from Jul 26–28 book + SCHW churn 2026-07-28):
- Do **not** sell losers just to chase a new scan name (that crystallized ESP/BANK/WMT losses).
- Stops and profit-takes are separate; rotation only frees capital from *winners*
  that already cleared a fee hurdle **with cushion**.
- Never rebuy the same symbol inside the cooldown after an exit (SCHW sold then
  bought ~12m later burned ~€50 fees for a near-flat round trip).
- We do not average-down into junk; hold quality through noise instead.
"""

from __future__ import annotations

from typing import Iterable, Set, Tuple

# Gross % moves (price vs avg buy), before commission.
DEFAULT_TAKE_PROFIT_PCT = 5.0
DEFAULT_STOP_LOSS_PCT = 5.0
# Revolut round-trip ≈ 0.5% + floors; need real edge before rotating a winner.
# SCHW was rotated at +1.6% then rebought — 1% was far too low.
DEFAULT_ROTATE_MIN_PROFIT_PCT = 3.0


def should_take_profit(profit_pct: float, *, threshold: float = DEFAULT_TAKE_PROFIT_PCT) -> bool:
    return profit_pct >= threshold


def should_stop_loss(profit_pct: float, *, threshold: float = DEFAULT_STOP_LOSS_PCT) -> bool:
    return profit_pct <= -abs(threshold)


def should_rebalance_exit(
    *,
    profit_pct: float,
    hold_seconds: float,
    min_hold_seconds: float,
    rotate_min_profit_pct: float = DEFAULT_ROTATE_MIN_PROFIT_PCT,
) -> Tuple[bool, str]:
    """
    Whether to sell a name that fell out of the top opportunity list.

    Returns (sell?, reason).
    """
    if hold_seconds < min_hold_seconds:
        return False, "min hold"

    # Never crystallize a loss just to rotate into the latest scan darling.
    if profit_pct < 0:
        return False, "no loss rotation"

    if profit_pct < rotate_min_profit_pct:
        return False, "below rotate hurdle"

    return True, "rotate winner"


def should_allow_rebuy(
    *,
    seconds_since_exit: float | None,
    cooldown_seconds: float,
) -> Tuple[bool, str]:
    """
    Block rebuying a symbol recently exited (anti flip-flop / fee burn).

    If never exited (seconds_since_exit is None), allow.
    """
    if seconds_since_exit is None:
        return True, "no recent exit"
    if cooldown_seconds <= 0:
        return True, "cooldown off"
    if seconds_since_exit < cooldown_seconds:
        return False, "rebuy cooldown"
    return True, "cooldown clear"


def opportunity_symbol_set(opportunities: Iterable[dict]) -> Set[str]:
    """All symbols currently on the opportunity list (not only top-N)."""
    out: Set[str] = set()
    for opp in opportunities or []:
        sym = opp.get("symbol") if isinstance(opp, dict) else None
        if sym:
            out.add(str(sym))
    return out


def crypto_entry_price_ok(price: float, *, min_usd: float = 1.0) -> bool:
    """Block sub-$1 meme pumps (ESP/BANK-style) from new entries."""
    try:
        return float(price) >= float(min_usd)
    except (TypeError, ValueError):
        return False
