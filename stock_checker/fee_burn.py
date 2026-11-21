#!/usr/bin/env python3
"""Warn when historical paper fees look like churn burn."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Tuple

from stock_checker.technical_indicators import _finite_signed

DEFAULT_FEE_BURN_PCT = 0.02


def _coerce_fee_burn_money(value: object) -> Optional[float]:
    """Cash/fees ≥0, or None when bool/gap/NaN (never ``True→€1`` / ``or 0``)."""
    if value is None or not _finite_signed(value):
        return None
    amount = float(value)  # type: ignore[arg-type]
    if amount < 0.0:
        return None
    return amount


def _coerce_fee_burn_pct(
    value: object, default: float = DEFAULT_FEE_BURN_PCT
) -> float:
    """Positive fee-burn fraction of capital, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``False→0%`` must not invent
    an always-high startup WARN, and ``True→100%`` must not clear a real burn
    (parity with desk ``build_fee_burn_glance`` threshold refuse).
    """
    if value is None or not _finite_signed(value):
        return float(default)
    pct = float(value)  # type: ignore[arg-type]
    if pct <= 0.0:
        return float(default)
    return pct


def fee_burn_facts(
    data_dir: str = "/data",
    *,
    fee_pct_of_capital: object = DEFAULT_FEE_BURN_PCT,
) -> Optional[dict[str, Any]]:
    """
    Return fee drag vs start capital when both are positive.

    Used by the desk glance (always) and the startup/pretrade warning (when high).
    """
    path = Path(data_dir) / "portfolio.json"
    if not path.exists():
        return None
    try:
        p = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap invents.
    initial = _coerce_fee_burn_money(p.get("initial_cash"))
    fees = _coerce_fee_burn_money(p.get("total_fees_paid"))
    if initial is None or fees is None or initial <= 0 or fees <= 0:
        return None

    thr = _coerce_fee_burn_pct(fee_pct_of_capital)
    ratio = fees / initial
    return {
        "fees": fees,
        "initial": initial,
        "ratio": ratio,
        "threshold": thr,
        "high": ratio >= thr,
    }


def fee_burn_warning(
    data_dir: str = "/data",
    *,
    fee_pct_of_capital: object = DEFAULT_FEE_BURN_PCT,
) -> Optional[str]:
    """
    Return a warning string if fees paid exceed fee_pct_of_capital of initial cash.
    """
    facts = fee_burn_facts(data_dir, fee_pct_of_capital=fee_pct_of_capital)
    if not facts or not facts["high"]:
        return None

    fees = float(facts["fees"])
    initial = float(facts["initial"])
    ratio = float(facts["ratio"])
    return (
        f"High fee burn: €{fees:,.2f} fees on €{initial:,.2f} capital "
        f"({ratio*100:.1f}%). Consider resetting paper book or raising min-hold-time."
    )


def maybe_print_fee_burn_warning(data_dir: str = "/data") -> Tuple[bool, str]:
    msg = fee_burn_warning(data_dir)
    if msg:
        print(f"⚠️  {msg}")
        return True, msg
    return False, ""
