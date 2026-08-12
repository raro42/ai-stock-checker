"""Soft entry gates (regime / RS / breadth) — shared by new trades and rebalance buys.

RS needs per-symbol I/O; callers pass a zero-arg check callback.
Fail-open soft allows are logged when a gate passes with a soft reason.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from .gate_audit import log_soft_allow
from .market_regime import new_entry_allowed
from .scan_breadth_gate import new_entry_breadth_allowed


def check_regime(
    *,
    is_crypto: bool,
    stock_regime: str,
    crypto_regime: str,
    enabled: bool,
) -> Tuple[bool, str]:
    ok, why = new_entry_allowed(
        is_crypto=is_crypto,
        stock_regime=stock_regime,
        crypto_regime=crypto_regime,
        enabled=enabled,
    )
    if ok:
        log_soft_allow("regime", why)
    return ok, why


def check_breadth(
    *,
    is_crypto: bool,
    pulse: Optional[Dict],
    enabled: bool,
) -> Tuple[bool, str]:
    ok, why = new_entry_breadth_allowed(
        is_crypto=is_crypto,
        pulse=pulse,
        enabled=enabled,
    )
    if ok:
        log_soft_allow("breadth", why)
    return ok, why


def soft_entry_gates_ok(
    *,
    is_crypto: bool,
    stock_regime: str,
    crypto_regime: str,
    regime_enabled: bool,
    rs_check: Callable[[], Tuple[bool, str]],
    breadth_pulse: Optional[Dict],
    breadth_enabled: bool,
) -> Tuple[bool, str]:
    """
    Run regime → RS → breadth in order.

    Returns (allowed, reason). Reason is the blocking gate message, or the
    last soft-pass reason when allowed.
    """
    ok, why = check_regime(
        is_crypto=is_crypto,
        stock_regime=stock_regime,
        crypto_regime=crypto_regime,
        enabled=regime_enabled,
    )
    if not ok:
        return False, f"regime gate ({why})"

    ok, why = rs_check()
    if not ok:
        return False, f"RS gate ({why})"
    log_soft_allow("rs", why)

    ok, why = check_breadth(
        is_crypto=is_crypto,
        pulse=breadth_pulse,
        enabled=breadth_enabled,
    )
    if not ok:
        return False, f"breadth gate ({why})"
    return True, why
