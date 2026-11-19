"""
Soft scan-breadth gate for new paper entries.

Inspired by external screener “market breadth” filters: skip *new* buys when the
latest scan list looks one-sided weak. Fail-open when there is no scan pulse.
Does not change exits or autoresearch.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence, Tuple

from stock_checker.technical_indicators import _finite_signed, coerce_nonneg_int

# Fraction of directional names that must be "up" (crypto) before new crypto buys.
DEFAULT_MIN_ADVANCE_RATIO = 0.40
# Stocks: require at least this many near-high / breakout-ish names on the scan list.
DEFAULT_MIN_STOCK_LEADERS = 1


def _pulse_count(value: object) -> int:
    """Non-neg pulse count; bool/gap/NaN → 0 (never ``True→1`` / ``False→0``).

    tradermonty #700/#655 + xang1234/portfolio AI — soft breadth gate must not
    invent a one-name advance / leader sample from a damaged bool pulse.
    """
    n = coerce_nonneg_int(value)
    return 0 if n is None else n


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
    # Env is always a string — parse digits; never int(True) from a bool knob.
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_MIN_STOCK_LEADERS
    if n < 0:
        return DEFAULT_MIN_STOCK_LEADERS
    return max(0, min(20, n))


def _is_crypto_symbol(symbol: str) -> bool:
    s = str(symbol).upper()
    return "-USD" in s or s.endswith("USDT") or s.endswith("USD")


def _change_pct(row: Mapping[str, Any]) -> Optional[float]:
    """Signed % for crypto A/D — refuse bool/gap/NaN (``True→1.0`` ≠ up).

    tradermonty #798/#655 + xang1234 breadth: soft gate must not invent advance.
    """
    for key in ("change_24h", "change_pct", "pct_change", "change"):
        if key not in row or row.get(key) is None:
            continue
        raw = row[key]
        if not _finite_signed(raw):
            continue
        return float(raw)
    return None


def _pct_from_high(row: Mapping[str, Any]) -> Optional[float]:
    """Near-high % for stock leaders — refuse bool/gap/NaN (``True→1.0`` ≠ leader)."""
    raw = row.get("pct_from_high")
    if raw is None:
        return None
    if not _finite_signed(raw):
        return None
    return float(raw)


def _score_near_high_fallback(row: Mapping[str, Any]) -> float:
    """Infer pct_from_high from enriched score band, else far-from-high.

    Unavailable/bool scores stay non-leaders (99) — never ``True→1.0`` invent.
    """
    raw = row.get("score")
    if not _finite_signed(raw):
        return 99.0
    score = float(raw)
    if 30.0 <= score <= 45.0:
        return score - 40.0
    return 99.0


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
            near = _pct_from_high(row)
            if near is None:
                # Fall back: stock score band is 40 + pct_from_high when enriched.
                near = _score_near_high_fallback(row)
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
        up = _pulse_count(pulse.get("crypto_up"))
        down = _pulse_count(pulse.get("crypto_down"))
        total = up + down
        if total <= 0:
            return True, "crypto breadth unknown — allow"
        ratio = up / float(total)
        if min_ratio is None:
            need = min_advance_ratio()
        elif isinstance(min_ratio, bool) or not _finite_signed(min_ratio):
            need = min_advance_ratio()
        else:
            need = max(0.05, min(0.95, float(min_ratio)))
        if ratio < need:
            return (
                False,
                f"crypto breadth weak ({up} up / {down} down = {ratio:.0%} < {need:.0%})",
            )
        return True, f"crypto breadth ok ({up} up / {down} down = {ratio:.0%})"

    leaders = _pulse_count(pulse.get("stock_leaders"))
    stock_n = _pulse_count(pulse.get("stock_n"))
    if stock_n <= 0:
        return True, "stock breadth unknown — allow"
    if min_leaders is None:
        need_n = min_stock_leaders()
    else:
        coerced = coerce_nonneg_int(min_leaders)
        need_n = min_stock_leaders() if coerced is None else coerced
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
        f"crypto {_pulse_count(pulse.get('crypto_up'))}↑/"
        f"{_pulse_count(pulse.get('crypto_down'))}↓ · "
        f"stock leaders {_pulse_count(pulse.get('stock_leaders'))}/"
        f"{_pulse_count(pulse.get('stock_n'))}"
    )
