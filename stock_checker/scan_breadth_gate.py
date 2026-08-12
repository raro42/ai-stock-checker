"""
Soft scan-breadth gate for new paper entries.

Inspired by external screener “market breadth” filters: skip *new* buys when the
latest scan list looks one-sided weak. Fail-open when there is no scan pulse.
Does not change exits or autoresearch.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

# Fraction of directional names that must be "up" (crypto) before new crypto buys.
DEFAULT_MIN_ADVANCE_RATIO = 0.40
# Stocks: require at least this many near-high / breakout-ish names on the scan list.
DEFAULT_MIN_STOCK_LEADERS = 1


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def breadth_gate_enabled() -> bool:
    """BREADTH_GATE=0 disables (default on)."""
    return os.getenv("BREADTH_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def min_advance_ratio() -> float:
    raw = os.getenv("BREADTH_MIN_ADVANCE", "").strip()
    if not raw:
        return DEFAULT_MIN_ADVANCE_RATIO
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_MIN_ADVANCE_RATIO
    return max(0.05, min(0.95, v))


def min_stock_leaders() -> int:
    raw = os.getenv("BREADTH_MIN_STOCK_LEADERS", "").strip()
    if not raw:
        return DEFAULT_MIN_STOCK_LEADERS
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_MIN_STOCK_LEADERS
    return max(0, min(20, n))


def _is_crypto_symbol(symbol: str) -> bool:
    s = str(symbol).upper()
    return "-USD" in s or s.endswith("USDT") or s.endswith("USD")


def _change_pct(row: Mapping[str, Any]) -> Optional[float]:
    for key in ("change_24h", "change_pct", "pct_change", "change"):
        if key not in row or row.get(key) is None:
            continue
        try:
            v = float(row[key])
        except (TypeError, ValueError):
            continue
        if _finite(v):
            return v
    return None


def pulse_from_opportunities(
    opportunities: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Build a tiny A/D pulse from the current scan list (not full-universe)."""
    rows = [r for r in (opportunities or []) if isinstance(r, Mapping)]
    crypto_up = crypto_down = 0
    stock_n = 0
    stock_near = 0
    crypto_missing_chg = 0
    for row in rows:
        sym = str(row.get("symbol") or "")
        if not sym:
            continue
        if _is_crypto_symbol(sym):
            chg = _change_pct(row)
            if chg is None:
                crypto_missing_chg += 1
                continue
            if chg > 0:
                crypto_up += 1
            elif chg < 0:
                crypto_down += 1
        else:
            stock_n += 1
            try:
                near = float(row.get("pct_from_high")) if row.get("pct_from_high") is not None else None
            except (TypeError, ValueError):
                near = None
            if near is None:
                # Fall back: stock score band is 40 + pct_from_high when enriched.
                try:
                    score = float(row.get("score") or 0)
                except (TypeError, ValueError):
                    score = 0.0
                if 30.0 <= score <= 45.0:
                    near = score - 40.0
                else:
                    near = 99.0
            if near <= 5.0:
                stock_near += 1
    return {
        "crypto_up": crypto_up,
        "crypto_down": crypto_down,
        "crypto_n": crypto_up + crypto_down,
        "crypto_missing_chg": crypto_missing_chg,
        "stock_n": stock_n,
        "stock_leaders": stock_near,
    }


def pulse_from_scan_lists(
    *,
    crypto_leaders: Sequence[Mapping[str, Any]] | None = None,
    stock_breakouts: Sequence[Mapping[str, Any]] | None = None,
    recommendations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prefer full leader/breakout lists; fall back to recommendations."""
    rows: list[Mapping[str, Any]] = []
    for src in (crypto_leaders, stock_breakouts):
        for row in src or []:
            if isinstance(row, Mapping):
                rows.append(row)
    if not rows:
        return pulse_from_opportunities(recommendations)
    return pulse_from_opportunities(rows)


def new_entry_breadth_allowed(
    *,
    is_crypto: bool,
    pulse: Mapping[str, Any] | None,
    enabled: bool = True,
    min_ratio: float | None = None,
    min_leaders: int | None = None,
) -> Tuple[bool, str]:
    """
    Soft gate for *new* entries from scan-list pulse.

    unknown / empty pulse → allow (fail open).
    """
    if not enabled:
        return True, "breadth gate off"
    if not isinstance(pulse, Mapping) or not pulse:
        return True, "scan breadth unknown — allow"

    if is_crypto:
        up = int(pulse.get("crypto_up") or 0)
        down = int(pulse.get("crypto_down") or 0)
        total = up + down
        if total <= 0:
            return True, "crypto breadth unknown — allow"
        ratio = up / float(total)
        need = min_advance_ratio() if min_ratio is None else float(min_ratio)
        if ratio < need:
            return (
                False,
                f"crypto breadth weak ({up} up / {down} down = {ratio:.0%} < {need:.0%})",
            )
        return True, f"crypto breadth ok ({up} up / {down} down = {ratio:.0%})"

    leaders = int(pulse.get("stock_leaders") or 0)
    stock_n = int(pulse.get("stock_n") or 0)
    if stock_n <= 0:
        return True, "stock breadth unknown — allow"
    need_n = min_stock_leaders() if min_leaders is None else int(min_leaders)
    if leaders < need_n:
        return (
            False,
            f"stock breadth thin ({leaders} leaders on scan < {need_n})",
        )
    return True, f"stock breadth ok ({leaders} leaders on scan)"


def summarize_pulse(pulse: Mapping[str, Any] | None) -> str:
    if not isinstance(pulse, Mapping) or not pulse:
        return "no scan pulse"
    return (
        f"crypto {int(pulse.get('crypto_up') or 0)}↑/"
        f"{int(pulse.get('crypto_down') or 0)}↓ · "
        f"stock leaders {int(pulse.get('stock_leaders') or 0)}/"
        f"{int(pulse.get('stock_n') or 0)}"
    )
