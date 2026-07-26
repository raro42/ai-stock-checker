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

# Daily SMA lookbacks — stocks slower, crypto faster (24/7).
STOCK_BENCHMARK = "SPY"
STOCK_SMA_PERIOD = 200
CRYPTO_BENCHMARK = "BTCUSDT"
CRYPTO_SMA_PERIOD = 50

REGIME_ON = "risk_on"
REGIME_OFF = "risk_off"
REGIME_UNKNOWN = "unknown"


def regime_gate_enabled() -> bool:
    """REGIME_GATE=0 disables the soft entry filter (default on)."""
    return os.getenv("REGIME_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def simple_sma(closes: Sequence[float], period: int) -> Optional[float]:
    if period <= 0 or len(closes) < period:
        return None
    window = closes[-period:]
    return sum(float(c) for c in window) / float(period)


def classify_close_vs_sma(closes: Sequence[float], period: int) -> str:
    """
    risk_on if last close >= SMA(period); risk_off if below; unknown if short history.
    """
    sma = simple_sma(closes, period)
    if sma is None or not closes:
        return REGIME_UNKNOWN
    last = float(closes[-1])
    if last >= sma:
        return REGIME_ON
    return REGIME_OFF


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
        "stock_benchmark": STOCK_BENCHMARK,
        "stock_sma_period": STOCK_SMA_PERIOD,
        "stock_regime": stock_regime,
        "stock_close": stock_close,
        "stock_sma": stock_sma,
        "crypto_benchmark": "BTC-USD",
        "crypto_sma_period": CRYPTO_SMA_PERIOD,
        "crypto_regime": crypto_regime,
        "crypto_close": crypto_close,
        "crypto_sma": crypto_sma,
        "detail": detail,
    }


def save_regime_snapshot(data_dir: Path | str, snap: dict[str, Any]) -> None:
    path = Path(data_dir) / "market_regime.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2) + "\n")
    except OSError:
        pass


def load_regime_snapshot(data_dir: Path | str) -> dict[str, Any]:
    path = Path(data_dir) / "market_regime.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def closes_from_yfinance_hist(hist_data: dict[str, Any]) -> list[float]:
    """Extract chronological closes from StockFetcher.get_historical_data payload."""
    rows = hist_data.get("data") if isinstance(hist_data, dict) else None
    if not isinstance(rows, dict) or not rows:
        return []
    closes: list[float] = []
    for _ts, bar in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if not isinstance(bar, dict):
            continue
        close = bar.get("Close", bar.get("close"))
        if close is None:
            continue
        try:
            closes.append(float(close))
        except (TypeError, ValueError):
            continue
    return closes


def closes_from_binance_klines(klines: list[dict[str, Any]] | None) -> list[float]:
    if not klines:
        return []
    out: list[float] = []
    for k in klines:
        if not isinstance(k, dict):
            continue
        try:
            out.append(float(k["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out
