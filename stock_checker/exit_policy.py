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
# Asymmetric on purpose (Aug 2026): thin +3% rotates lost to −5% stops.
DEFAULT_TAKE_PROFIT_PCT = 8.0
DEFAULT_STOP_LOSS_PCT = 5.0
# Revolut round-trip ≈ 0.5% + floors; rotate only when edge clears a full stop-sized win.
# Was 3.0% — too easy to bank thin winners then refill into breakouts that stop out.
DEFAULT_ROTATE_MIN_PROFIT_PCT = 5.0


def exit_thresholds_for_asset(*, is_crypto: bool) -> Tuple[float, float]:
    """
    Stocks: take-profit +8% / stop −5%. Crypto majors use wider bands (crypto_policy).

    Returns (take_profit_pct, stop_loss_pct) as positive magnitudes.
    """
    if is_crypto:
        from .crypto_policy import crypto_exit_thresholds

        return crypto_exit_thresholds()
    return DEFAULT_TAKE_PROFIT_PCT, DEFAULT_STOP_LOSS_PCT


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


def book_action_mode(n_holdings: int, max_positions: int) -> str:
    """
    Trading posture from book size vs Ops max.

    - open: room for new entries
    - at_cap: no new entries; rotation still allowed under exit_policy
    - overweight: TP/SL plus slow trim-to-cap (not scan rotation)
      (legacy books opened under a higher max must shrink via exits, not churn)
    """
    try:
        n = int(n_holdings)
        cap = int(max_positions)
    except (TypeError, ValueError):
        return "open"
    if cap < 1:
        cap = 1
    if n > cap:
        return "overweight"
    if n >= cap:
        return "at_cap"
    return "open"


def pick_overweight_trim_candidate(
    rows: Iterable[dict],
    *,
    min_hold_seconds: float,
) -> Tuple[str | None, str]:
    """
    When overweight, pick one name to exit so the book can return to max_positions.

    Rules (anti-churn, not scan-chase):
    - Must be past min hold (same floor as normal exits).
    - Prefer a **winner** first (weakest winner) so we free a slot without
      crystallizing a −2% mark when a green name exists (Aug 28 trim lesson).
    - If no winner past min hold, prefer the weakest mark (lowest unrealized %).
    - Returns one candidate; caller may loop until at_cap while eligible.
    """
    eligible: list[tuple[float, str]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol")
        if not sym:
            continue
        try:
            hold = float(row.get("hold_seconds") or 0)
            pnl = float(row.get("profit_pct"))
        except (TypeError, ValueError):
            continue
        if hold < float(min_hold_seconds):
            continue
        eligible.append((pnl, str(sym)))

    if not eligible:
        return None, "no trim candidates past min hold"

    winners = [t for t in eligible if t[0] > 0]
    if winners:
        winners.sort(key=lambda t: t[0])  # weakest winner first
        pnl, sym = winners[0]
        return sym, f"trim overweight (winner {pnl:+.2f}%)"

    eligible.sort(key=lambda t: t[0])  # worst first
    pnl, sym = eligible[0]
    return sym, f"trim overweight (worst mark {pnl:+.2f}%)"


def crypto_entry_price_ok(price: float, *, min_usd: float = 1.0) -> bool:
    """Block sub-$1 meme pumps (ESP/BANK-style) from new entries."""
    try:
        return float(price) >= float(min_usd)
    except (TypeError, ValueError):
        return False
