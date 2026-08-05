"""
Soft relative-strength gate for new paper entries.

Inspired by external screener “RS as primary filter”: only block *new* buys when
the name underperforms its benchmark over a lookback window. Existing holds are
untouched. Fail-open on short history / missing data.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence, Tuple

# ~3 months of sessions (RyanJHamby / Minervini-style RS window).
DEFAULT_RS_LOOKBACK = 63
STOCK_BENCHMARK = "SPY"
CRYPTO_BENCHMARK = "BTCUSDT"


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


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
    return max(5, min(252, n))


def period_return(closes: Sequence[float], lookback: int) -> Optional[float]:
    """
    Return over `lookback` steps: (last / close[-lookback-1]) - 1.

    Needs lookback+1 finite closes. Returns None if insufficient or invalid.
    """
    if lookback <= 0:
        return None
    clean = [float(c) for c in closes if _finite(float(c))]
    need = lookback + 1
    if len(clean) < need:
        return None
    start = clean[-need]
    end = clean[-1]
    if start <= 0 or end <= 0:
        return None
    return (end / start) - 1.0


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

    Returns (allowed, reason).
    """
    asset_ret = period_return(asset_closes, lookback)
    bench_ret = period_return(bench_closes, lookback)
    if asset_ret is None or bench_ret is None:
        return True, f"{asset_label} RS unknown — allow"
    if asset_ret >= bench_ret:
        return (
            True,
            f"{asset_label} RS ok ({asset_ret:+.1%} vs {bench_label} {bench_ret:+.1%})",
        )
    return (
        False,
        f"{asset_label} lagging {bench_label} "
        f"({asset_ret:+.1%} vs {bench_ret:+.1%} over {lookback}d)",
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
    """
    if not enabled:
        return True, "RS gate off"
    lb = DEFAULT_RS_LOOKBACK if lookback is None else int(lookback)
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
