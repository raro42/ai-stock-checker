"""
Soft relative-strength gate for new paper entries.

Inspired by external screener “RS as primary filter”: only block *new* buys when
the name underperforms its benchmark over a lookback window. Existing holds are
untouched. Fail-open on short history / missing data / gappy anchors.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence, Tuple

from stock_checker.technical_indicators import _valid_close, coerce_nonneg_int

# ~3 months of sessions (RyanJHamby / Minervini-style RS window).
DEFAULT_RS_LOOKBACK = 63
STOCK_BENCHMARK = "SPY"
CRYPTO_BENCHMARK = "BTCUSDT"
# xang1234 #539: reject RS when >25% of the positional lookback misses anchors
# (silent NaN-drop compresses the window and invents relative strength).
RS_ANCHOR_MAX_MISS = 0.25


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def _coerce_rs_lookback(lookback: object) -> Optional[int]:
    """Positive RS window days, or None when bool/gap/NaN (never ``True→1d``).

    tradermonty #700/#655 + xang1234/portfolio AI after regime SMA period refuse:
    ``int(True)`` must not invent a 1-day RS read.
    """
    n = coerce_nonneg_int(lookback)
    if n is None or n <= 0:
        return None
    return n


def rs_gate_enabled() -> bool:
    """RS_GATE=0 disables the soft entry filter (default on)."""
    return os.getenv("RS_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def rs_lookback() -> int:
    """RS_LOOKBACK env override; clamped to a sane daily window."""
    raw = os.getenv("RS_LOOKBACK", "").strip()
    if not raw:
        return DEFAULT_RS_LOOKBACK
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_RS_LOOKBACK
    if n <= 0:
        return DEFAULT_RS_LOOKBACK
    return max(5, min(252, n))


def rs_anchor_max_miss() -> float:
    """Max positional NaN share before RS fail-opens as anchor gap.

    ``RS_ANCHOR_MAX_MISS`` env override is a share in ``[0, 1]`` (1 disables
    the gap guard). xang1234 #539 30c6c2d: out-of-range / NaN / typo must not
    turn the guarded path into a hard failure — fall back to the default.
    """
    raw = os.getenv("RS_ANCHOR_MAX_MISS", "").strip()
    if not raw:
        return float(RS_ANCHOR_MAX_MISS)
    try:
        value = float(raw)
    except ValueError:
        return float(RS_ANCHOR_MAX_MISS)
    if not _finite(value) or not 0.0 <= value <= 1.0:
        return float(RS_ANCHOR_MAX_MISS)
    return float(value)


def anchor_miss_ratio(closes: Sequence[float], lookback: int) -> Optional[float]:
    """
    Fraction of unusable bars in the last lookback+1 *positional* slots.

    Bool / gap / zero / NaN / non-numeric count as misses (tradermonty #796 /
    #655 — never ``float(True)→1.0``). None when shorter than the window.
    Bool lookback → None (never ``True→1d`` miss invent).
    """
    lb = _coerce_rs_lookback(lookback)
    if lb is None:
        return None
    need = lb + 1
    if len(closes) < need:
        return None
    window = closes[-need:]
    miss = sum(1 for c in window if not _valid_close(c))
    return miss / float(need)


def period_return(closes: Sequence[float], lookback: int) -> Optional[float]:
    """
    Return over `lookback` steps on a positional window: (last / first) - 1.

    Needs lookback+1 raw slots with valid start+end anchors and miss rate
    ≤ ``rs_anchor_max_miss()``. Does not drop holes to steal older bars
    (anchor-gap honesty). Returns None if insufficient, gappy, or invalid
    (tradermonty #796: bool/gap/zero/NaN endpoints are unavailable RS).
    Bool lookback → None (never ``True→1d`` return invent).
    """
    lb = _coerce_rs_lookback(lookback)
    if lb is None:
        return None
    need = lb + 1
    if len(closes) < need:
        return None
    window = closes[-need:]
    miss = sum(1 for c in window if not _valid_close(c)) / float(need)
    if miss > rs_anchor_max_miss():
        return None
    start, end = window[0], window[-1]
    if not _valid_close(start) or not _valid_close(end):
        return None
    return (float(end) / float(start)) - 1.0


def beats_benchmark(
    asset_closes: Sequence[float],
    bench_closes: Sequence[float],
    lookback: int,
    *,
    asset_label: str = "asset",
    bench_label: str = "benchmark",
) -> Tuple[bool, str]:
    """
    True if asset period return >= benchmark (or data missing → fail-open allow).

    Returns (allowed, reason). Anchor-gap miss above ``rs_anchor_max_miss()``
    fail-opens distinctly so soft-allow audit does not treat a compressed
    lookback as a real RS read. Bool lookback fail-opens (never ``True→1d``).
    """
    lb = _coerce_rs_lookback(lookback)
    if lb is None:
        return True, f"{asset_label} RS unknown — lookback unreadable — allow"
    gap_ceil = rs_anchor_max_miss()
    asset_miss = anchor_miss_ratio(asset_closes, lb)
    bench_miss = anchor_miss_ratio(bench_closes, lb)
    # xang1234 #668: young / short listings are not gappy-anchor holes —
    # series shorter than lookback+1 is short history, not inventable RS.
    if asset_miss is None:
        return True, f"{asset_label} RS unknown — short history — allow"
    if bench_miss is None:
        return True, f"{bench_label} RS unknown — short history — allow"
    if asset_miss > gap_ceil:
        return True, f"{asset_label} RS unknown — anchor gap — allow"
    if bench_miss > gap_ceil:
        return True, f"{bench_label} RS unknown — anchor gap — allow"

    asset_ret = period_return(asset_closes, lb)
    bench_ret = period_return(bench_closes, lb)
    if asset_ret is None or bench_ret is None:
        # Start/end hole inside an otherwise tolerable miss budget.
        if asset_ret is None and asset_miss > 0:
            return True, f"{asset_label} RS unknown — anchor gap — allow"
        if bench_ret is None and bench_miss > 0:
            return True, f"{bench_label} RS unknown — anchor gap — allow"
        return True, f"{asset_label} RS unknown — allow"
    if asset_ret >= bench_ret:
        return (
            True,
            f"{asset_label} RS ok ({asset_ret:+.1%} vs {bench_label} {bench_ret:+.1%})",
        )
    return (
        False,
        f"{asset_label} lagging {bench_label} "
        f"({asset_ret:+.1%} vs {bench_ret:+.1%} over {lb}d)",
    )


def new_entry_rs_allowed(
    *,
    symbol: str,
    is_crypto: bool,
    asset_closes: Sequence[float] | None,
    spy_closes: Sequence[float] | None,
    btc_closes: Sequence[float] | None,
    lookback: int | None = None,
    enabled: bool = True,
) -> Tuple[bool, str]:
    """
    Soft RS gate for *new* entries only.

    Benchmark symbols (SPY / BTCUSDT) always pass. Gate off / missing series → allow.
    Bool lookback falls back to ``DEFAULT_RS_LOOKBACK`` (never ``True→1d``).
    """
    if not enabled:
        return True, "RS gate off"
    if lookback is None:
        lb = DEFAULT_RS_LOOKBACK
    else:
        coerced = _coerce_rs_lookback(lookback)
        lb = DEFAULT_RS_LOOKBACK if coerced is None else coerced
    sym = str(symbol).upper().replace("-USD", "USDT")
    if not is_crypto and str(symbol).upper() in {"SPY", "SPX"}:
        return True, "SPY is the stock benchmark"
    if is_crypto and sym in {"BTCUSDT", "BTC"}:
        return True, "BTC is the crypto benchmark"

    if is_crypto:
        if not asset_closes or not btc_closes:
            return True, "BTC RS unknown — allow"
        return beats_benchmark(
            asset_closes,
            btc_closes,
            lb,
            asset_label=str(symbol),
            bench_label="BTC",
        )

    if not asset_closes or not spy_closes:
        return True, "SPY RS unknown — allow"
    return beats_benchmark(
        asset_closes,
        spy_closes,
        lb,
        asset_label=str(symbol),
        bench_label="SPY",
    )
