"""
ATR-based stop / rough R:R notes for desk screener (display only).

Does not place trades. Inspired by external screener risk framing:
stop ≈ entry − 2×ATR (or swing low), target ≈ +20% for a simple R:R check.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    period: int = 14,
) -> Optional[float]:
    if period <= 0 or len(closes) < period + 1:
        return None
    if not (len(highs) == len(lows) == len(closes)):
        return None
    trs: list[float] = []
    for i in range(1, len(closes)):
        try:
            h, l, pc = float(highs[i]), float(lows[i]), float(closes[i - 1])
        except (TypeError, ValueError):
            return None
        if not all(_finite(v) for v in (h, l, pc)):
            return None
        trs.append(true_range(h, l, pc))
    if len(trs) < period:
        return None
    window = trs[-period:]
    return sum(window) / float(period)


def risk_reward_note(
    *,
    entry: float,
    atr: Optional[float],
    swing_low: Optional[float] = None,
    atr_mult: float = 2.0,
    target_pct: float = 0.20,
    min_rr: float = 2.0,
) -> dict[str, Any]:
    """
    Build a soft risk note for UI.

    Stop = max(entry − atr_mult×ATR, swing_low×0.98) when both exist (more
    conservative = higher stop). Fail soft when inputs missing.
    """
    out: dict[str, Any] = {
        "entry": None,
        "stop": None,
        "target": None,
        "risk_pct": None,
        "reward_pct": None,
        "rr": None,
        "rr_ok": None,
        "stop_type": "none",
        "summary": "risk n/a",
    }
    try:
        e = float(entry)
    except (TypeError, ValueError):
        return out
    if not _finite(e) or e <= 0:
        return out
    out["entry"] = e
    out["target"] = e * (1.0 + float(target_pct))
    out["reward_pct"] = float(target_pct) * 100.0

    atr_stop = None
    if atr is not None and _finite(float(atr)) and float(atr) > 0:
        atr_stop = e - float(atr_mult) * float(atr)

    swing_stop = None
    if swing_low is not None and _finite(float(swing_low)) and float(swing_low) > 0:
        swing_stop = float(swing_low) * 0.98

    stop = None
    stop_type = "none"
    if atr_stop is not None and swing_stop is not None:
        # Higher stop = less risk distance (more conservative placement).
        if atr_stop >= swing_stop:
            stop, stop_type = atr_stop, "atr"
        else:
            stop, stop_type = swing_stop, "swing"
    elif atr_stop is not None:
        stop, stop_type = atr_stop, "atr"
    elif swing_stop is not None:
        stop, stop_type = swing_stop, "swing"

    if stop is None or stop >= e:
        out["summary"] = "risk n/a (stop ≥ entry)"
        return out

    risk = e - stop
    risk_pct = risk / e
    reward = out["target"] - e
    rr = reward / risk if risk > 0 else None
    out["stop"] = stop
    out["stop_type"] = stop_type
    out["risk_pct"] = risk_pct * 100.0
    out["rr"] = rr
    out["rr_ok"] = bool(rr is not None and rr >= float(min_rr))
    flag = "ok" if out["rr_ok"] else "thin"
    out["summary"] = (
        f"stop {stop_type} €{stop:.2f} (−{risk_pct*100:.1f}%) · "
        f"tgt +{target_pct*100:.0f}% · R:R {rr:.1f} ({flag})"
        if rr is not None
        else f"stop {stop_type} €{stop:.2f}"
    )
    return out


def note_from_day_range(
    *,
    entry: float,
    day_high: Optional[float] = None,
    day_low: Optional[float] = None,
    volatility_pct: Optional[float] = None,
) -> dict[str, Any]:
    """
    Soft risk note when we only have a day range or a volatility %.

    Day range stands in for 1×ATR; crypto often passes volatility_pct instead.
    Display-only — not an exit order.
    """
    atr = None
    try:
        e = float(entry)
    except (TypeError, ValueError):
        return risk_reward_note(entry=0.0, atr=None)
    if day_high is not None and day_low is not None:
        try:
            hi, lo = float(day_high), float(day_low)
            if _finite(hi) and _finite(lo) and hi > lo > 0:
                atr = hi - lo
        except (TypeError, ValueError):
            atr = None
    if atr is None and volatility_pct is not None and _finite(float(volatility_pct)):
        # Treat quoted volatility % as a rough ATR% of price.
        atr = e * (abs(float(volatility_pct)) / 100.0)
    swing = None
    if day_low is not None:
        try:
            swing = float(day_low)
        except (TypeError, ValueError):
            swing = None
    return risk_reward_note(entry=e, atr=atr, swing_low=swing)


def note_from_ohlc_rows(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    entry: Optional[float] = None,
    atr_period: int = 14,
    swing_lookback: int = 20,
) -> dict[str, Any]:
    """Compute ATR note from chronological OHLCV-like dict rows."""
    if not rows:
        return risk_reward_note(entry=entry or 0.0, atr=None)
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        try:
            h = float(r.get("high", r.get("High")))
            l = float(r.get("low", r.get("Low")))
            c = float(r.get("close", r.get("Close")))
        except (TypeError, ValueError):
            continue
        if _finite(h) and _finite(l) and _finite(c):
            highs.append(h)
            lows.append(l)
            closes.append(c)
    if not closes:
        return risk_reward_note(entry=entry or 0.0, atr=None)
    px = float(entry) if entry is not None else closes[-1]
    atr = average_true_range(highs, lows, closes, period=atr_period)
    swing = None
    if len(lows) >= 2:
        window = lows[-min(swing_lookback, len(lows)) :]
        swing = min(window) if window else None
    return risk_reward_note(entry=px, atr=atr, swing_low=swing)
