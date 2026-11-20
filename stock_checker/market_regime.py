"""
Soft market-regime gate for new paper entries.

Inspired by external screener “market regime filtering”: only block *new* buys
when the reference trend is below its SMA. Existing holds are untouched.
Does not change autoresearch / promote rules.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from stock_checker.technical_indicators import coerce_nonneg_int

# Daily SMA lookbacks — stocks slower, crypto faster (24/7).
# SPY is an S&P 500 *ETF proxy*, not the official ^GSPC index
# (tradermonty #765 instrument identity — prices/volume are SPY's own).
STOCK_BENCHMARK = "SPY"
STOCK_BENCHMARK_KIND = "etf_proxy"
STOCK_BENCHMARK_NOT = "^GSPC"
STOCK_BENCHMARK_IDENTITY = "SPY · ETF proxy · not ^GSPC"
STOCK_SMA_PERIOD = 200
# BTCUSDT is a Binance spot pair for regime/RS SMA — not Yahoo BTC-USD
# (paper live symbols) and not a CMC aggregate index (tradermonty #765/#766).
CRYPTO_BENCHMARK = "BTCUSDT"
CRYPTO_BENCHMARK_KIND = "binance_pair"
CRYPTO_BENCHMARK_NOT = "BTC-USD"
CRYPTO_BENCHMARK_IDENTITY = "BTCUSDT · Binance pair · not BTC-USD"
CRYPTO_SMA_PERIOD = 50

REGIME_ON = "risk_on"
REGIME_OFF = "risk_off"
REGIME_UNKNOWN = "unknown"
# Close within this fraction of its SMA is not a comparable regime episode.
# Display only — the entry gate still uses the binary close-vs-SMA label.
REGIME_WEAK_ANALOGUE_FRAC = 0.005


def regime_gate_enabled() -> bool:
    """REGIME_GATE=0 disables the soft entry filter (default on)."""
    return os.getenv("REGIME_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def _valid_sma_close(price: object) -> bool:
    """tradermonty #655/#754 + portfolio AI claim honesty: SMA bars must be
    real finite positive closes. Gap/zero/NaN is not a shorter window."""
    if isinstance(price, bool):
        return False
    try:
        value = float(price)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return _finite(value) and value > 0.0


def simple_sma(closes: Sequence[float], period: int) -> Optional[float]:
    # tradermonty #700/#655: refuse bool period — True→SMA(1) invent.
    n = coerce_nonneg_int(period)
    if n is None or n <= 0 or len(closes) < n:
        return None
    window = list(closes[-n:])
    # Do not drop bad bars — a hole is unavailable, not a compressed SMA
    if any(not _valid_sma_close(c) for c in window):
        return None
    return sum(float(c) for c in window) / float(n)


def classify_close_vs_sma(closes: Sequence[float], period: int) -> str:
    """
    risk_on if last close >= SMA(period); risk_off if below; unknown if short
    history or any gap/zero/NaN in the SMA window (never strip bad bars).
    """
    n = coerce_nonneg_int(period)
    if n is None or n <= 0 or len(closes) < n:
        return REGIME_UNKNOWN
    sma = simple_sma(closes, n)
    if sma is None:
        return REGIME_UNKNOWN
    last = float(closes[-1])
    if last >= sma:
        return REGIME_ON
    return REGIME_OFF


def stock_benchmark_identity() -> dict[str, str]:
    """Desk/API identity for the equity regime/RS bench (display only).

    Friends must not read ``SPY`` as the S&P 500 index — SMA and RS use the
    ETF's own series (tradermonty #765 instrument identity). Not a new gate.
    """
    return {
        "symbol": STOCK_BENCHMARK,
        "kind": STOCK_BENCHMARK_KIND,
        "not_index": STOCK_BENCHMARK_NOT,
        "bit": STOCK_BENCHMARK_IDENTITY,
    }


def crypto_benchmark_identity() -> dict[str, str]:
    """Desk/API identity for the crypto regime/RS bench (display only).

    Friends must not read bare ``BTC`` as Yahoo ``BTC-USD`` (paper symbols) —
    SMA and RS use the Binance ``BTCUSDT`` series. Not a new gate.
    """
    return {
        "symbol": CRYPTO_BENCHMARK,
        "kind": CRYPTO_BENCHMARK_KIND,
        "not_yahoo": CRYPTO_BENCHMARK_NOT,
        "bit": CRYPTO_BENCHMARK_IDENTITY,
    }


def regime_analogue_label(
    regime: str,
    close: Optional[float] = None,
    sma: Optional[float] = None,
    *,
    weak_frac: float = REGIME_WEAK_ANALOGUE_FRAC,
) -> str:
    """Desk label for one SMA sleeve. Display only.

    ``risk_on`` / ``risk_off`` is a heuristic (last close vs SMA), not a
    calibrated market-top probability. Missing prices, or a close within
    ``weak_frac`` of the SMA, refuse that name — a weak separation is not
    a comparable episode. The entry gate is unchanged.
    """
    name = str(regime or "").strip()
    if name in {"", "—"}:
        return "—"
    if name == REGIME_UNKNOWN:
        return REGIME_UNKNOWN
    last = _json_float(close)
    average = _json_float(sma)
    if last is None or average is None or average == 0:
        return "no analogue"
    # Refuse bool weak_frac — True→1.0 would mark every sleeve "near SMA".
    frac = _json_float(weak_frac)
    if frac is None or frac < 0.0:
        frac = REGIME_WEAK_ANALOGUE_FRAC
    if abs(last - average) / abs(average) < frac:
        return "near SMA"
    return f"{name} · heuristic"


def new_entry_allowed(
    *,
    is_crypto: bool,
    stock_regime: str,
    crypto_regime: str,
    enabled: bool = True,
) -> Tuple[bool, str]:
    """
    Soft gate for *new* entries only.

    unknown → allow (fail open so a data blip does not freeze the desk).
    """
    if not enabled:
        return True, "regime gate off"
    regime = crypto_regime if is_crypto else stock_regime
    label = "BTC" if is_crypto else "SPY"
    if regime == REGIME_OFF:
        return False, f"{label} risk-off (below SMA)"
    if regime == REGIME_UNKNOWN:
        return True, f"{label} regime unknown — allow"
    return True, f"{label} risk-on"


def _json_float(value: Optional[float]) -> Optional[float]:
    """Finite float, or None when bool/gap/NaN (never ``True→1.0``).

    tradermonty #700/#655 + xang1234/portfolio AI: damaged ``market_regime.json``
    or analogue args must not invent $1 closes / SMA prints for desk labels.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if _finite(v) else None


def snapshot_dict(
    *,
    stock_regime: str,
    crypto_regime: str,
    stock_sma: Optional[float] = None,
    crypto_sma: Optional[float] = None,
    stock_close: Optional[float] = None,
    crypto_close: Optional[float] = None,
    enabled: bool = True,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enabled": enabled,
        "score_kind": "heuristic_sma",
        "calibrated_probability": False,
        "stock_benchmark": STOCK_BENCHMARK,
        "stock_benchmark_kind": STOCK_BENCHMARK_KIND,
        "stock_benchmark_not": STOCK_BENCHMARK_NOT,
        "stock_benchmark_identity": STOCK_BENCHMARK_IDENTITY,
        "stock_sma_period": STOCK_SMA_PERIOD,
        "stock_regime": stock_regime,
        "stock_close": _json_float(stock_close),
        "stock_sma": _json_float(stock_sma),
        "crypto_benchmark": CRYPTO_BENCHMARK,
        "crypto_benchmark_kind": CRYPTO_BENCHMARK_KIND,
        "crypto_benchmark_not": CRYPTO_BENCHMARK_NOT,
        "crypto_benchmark_identity": CRYPTO_BENCHMARK_IDENTITY,
        "crypto_sma_period": CRYPTO_SMA_PERIOD,
        "crypto_regime": crypto_regime,
        "crypto_close": _json_float(crypto_close),
        "crypto_sma": _json_float(crypto_sma),
        "detail": detail,
    }


def save_regime_snapshot(data_dir: Path | str, snap: dict[str, Any]) -> None:
    path = Path(data_dir) / "market_regime.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2, allow_nan=False) + "\n")
    except OSError:
        pass


def load_regime_snapshot(data_dir: Path | str) -> dict[str, Any]:
    path = Path(data_dir) / "market_regime.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _close_or_nan(raw: object) -> float:
    """Positional close for regime/RS loaders.

    Gap/zero/NaN/non-numeric stays ``nan`` so callers see a hole instead of a
    silently shortened series (xang1234 / portfolio AI claim honesty; same
    lineage as ``simple_sma`` refuse-to-strip).
    """
    if isinstance(raw, bool):
        return float("nan")
    try:
        val = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")
    if not _finite(val) or val <= 0.0:
        return float("nan")
    return val


def closes_from_yfinance_hist(hist_data: dict[str, Any]) -> list[float]:
    """Extract chronological closes from StockFetcher.get_historical_data payload.

    Invalid / missing closes keep a ``nan`` slot (do not drop bars).
    """
    rows = hist_data.get("data") if isinstance(hist_data, dict) else None
    if not isinstance(rows, dict) or not rows:
        return []
    closes: list[float] = []
    for _ts, bar in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if not isinstance(bar, dict):
            closes.append(float("nan"))
            continue
        close = bar.get("Close", bar.get("close"))
        closes.append(_close_or_nan(close))
    return closes


def closes_from_binance_klines(klines: list[dict[str, Any]] | None) -> list[float]:
    """Extract closes; bad/missing candles keep a ``nan`` slot (no compress)."""
    if not klines:
        return []
    out: list[float] = []
    for k in klines:
        if not isinstance(k, dict):
            out.append(float("nan"))
            continue
        out.append(_close_or_nan(k.get("close")))
    return out
