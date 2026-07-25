#!/usr/bin/env python3
"""Warn when historical paper fees look like churn burn."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple


def fee_burn_warning(
    data_dir: str = "/data",
    *,
    fee_pct_of_capital: float = 0.02,
) -> Optional[str]:
    """
    Return a warning string if fees paid exceed fee_pct_of_capital of initial cash.
    """
    path = Path(data_dir) / "portfolio.json"
    if not path.exists():
        return None
    try:
        p = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    initial = float(p.get("initial_cash") or 0)
    fees = float(p.get("total_fees_paid") or 0)
    if initial <= 0 or fees <= 0:
        return None

    ratio = fees / initial
    if ratio < fee_pct_of_capital:
        return None

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
