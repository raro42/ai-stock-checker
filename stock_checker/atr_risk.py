"""
ATR-based stop / rough R:R notes for desk screener (display only).

Does not place trades. Inspired by external screener risk framing:
stop ≈ entry − 2×ATR (or swing low), target ≈ +20% for a simple R:R check.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from stock_checker.technical_indicators import (
    TechnicalIndicators,
    _finite_signed,
    _valid_close,
    _valid_ohlc_bar,
)

# Soft Screener framing only — live stock exits use exit_policy TP/SL, not ATR.
DEFAULT_ATR_MULT = 2.0
DEFAULT_ATR_TARGET_PCT = 0.20
DEFAULT_ATR_MIN_RR = 2.0


def average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    period: int = 14,
) -> Optional[float]:
    """Wilder ATR (RMA) for Screener notes — same math as ``TechnicalIndicators``.

    xang1234 #749: trailing SMA / span-EMA of true range is not Wilder.
    tradermonty #655/#798: validate OHLC *before* ``float()`` so ``True→1.0``
    cannot invent a Screener stop. Display-only; live exits stay TP/SL.
    """
    if len(highs) != len(lows) or len(highs) != len(closes):
        return None
    h: list[float] = []
    lo: list[float] = []
    c: list[float] = []
    for hi, low, close in zip(highs, lows, closes):
        if not _valid_ohlc_bar(hi, low, close):
            return None
        h.append(float(hi))
        lo.append(float(low))
        c.append(float(close))
    return TechnicalIndicators.calculate_atr(h, lo, c, period=period)


def risk_reward_note(
    *,
    entry: float,
    atr: Optional[float],
    swing_low: Optional[float] = None,
    atr_mult: float = DEFAULT_ATR_MULT,
    target_pct: float = DEFAULT_ATR_TARGET_PCT,
    min_rr: float = DEFAULT_ATR_MIN_RR,
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
    # tradermonty #655/#798: never ``float(True)`` → invent €1 entry / stop.
    if not _valid_close(entry):
        return out
    if not (_finite_signed(target_pct) and _finite_signed(atr_mult) and _finite_signed(min_rr)):
        return out
    e = float(entry)
    out["entry"] = e
    out["target"] = e * (1.0 + float(target_pct))
    out["reward_pct"] = float(target_pct) * 100.0

    atr_stop = None
    if atr is not None and _valid_close(atr):
        atr_stop = e - float(atr_mult) * float(atr)

    swing_stop = None
    if swing_low is not None and _valid_close(swing_low):
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

    if stop is None:
        out["summary"] = "risk n/a (stop ≥ entry)"
        return out

    # tradermonty #813: report risk against the monetized (cent) stop, not
    # raw atr×mult — display stop and −risk% must agree with €stop.2f.
    reported = round(float(stop), 2)
    if not (0.0 < reported < e):
        out["summary"] = "risk n/a (stop ≥ entry)"
        return out

    risk = e - reported
    risk_pct = risk / e
    reward = out["target"] - e
    rr = reward / risk if risk > 0 else None
    out["stop"] = reported
    out["stop_type"] = stop_type
    out["risk_pct"] = risk_pct * 100.0
    out["rr"] = rr
    out["rr_ok"] = bool(rr is not None and rr >= float(min_rr))
    flag = "ok" if out["rr_ok"] else "thin"
    out["summary"] = (
        f"stop {stop_type} €{reported:.2f} (−{risk_pct*100:.1f}%) · "
        f"tgt +{target_pct*100:.0f}% · R:R {rr:.1f} ({flag})"
        if rr is not None
        else f"stop {stop_type} €{reported:.2f}"
    )
    return out


def risk_note_has_vol(summary: str | None) -> bool:
    """True when a Screener risk note has a stop (vol proxy), not soft n/a.

    staskh-style honesty: missing vol must be visible. Desk soft-n/a (display);
    does not refuse entries — live exits stay exit_policy TP/SL.
    """
    s = (summary or "").strip().lower()
    if not s or s.startswith("risk n/a"):
        return False
    return s.startswith("stop ")


def atr_vol_coverage(
    rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Count Screener rows with usable ATR/vol notes vs soft n/a (display only)."""
    total = 0
    with_vol = 0
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        note = row.get("risk_note")
        if note is None and row.get("summary") is not None:
            note = row.get("summary")
        # Count only rows that carry a risk_note field (incl. empty / n/a).
        if "risk_note" not in row and "summary" not in row:
            continue
        total += 1
        if risk_note_has_vol(str(note) if note is not None else ""):
            with_vol += 1
    missing = max(0, total - with_vol)
    pct = round(100.0 * with_vol / total, 1) if total else None
    return {
        "total": total,
        "with_vol": with_vol,
        "missing": missing,
        "coverage_pct": pct,
    }


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
    swing = None
    if not _valid_close(entry):
        return risk_reward_note(entry=0.0, atr=None)
    e = float(entry)
    day_ok = False
    if day_high is not None and day_low is not None:
        # tradermonty/#655 + xang1234 OHLC integrity: entry must sit in
        # [low, high] or the day range is not a usable ATR/swing proxy.
        # Validate *before* float so bool/gap cannot invent a day ATR.
        if _valid_ohlc_bar(day_high, day_low, e):
            hi, lo = float(day_high), float(day_low)
            if hi > lo:
                atr = hi - lo
                swing = lo
                day_ok = True
    if atr is None and volatility_pct is not None and _finite_signed(volatility_pct):
        # Treat quoted volatility % as a rough ATR% of price (signed ok; abs).
        atr = e * (abs(float(volatility_pct)) / 100.0)
        if not _valid_close(atr):
            atr = None
    # Bare day_low without a coherent day OHLC must not invent a swing stop.
    if swing is None and not day_ok and day_low is not None and day_high is None:
        if _valid_close(day_low):
            swing = float(day_low)
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
            # Non-bar slot would compress the series — refuse the note.
            return risk_reward_note(entry=entry or 0.0, atr=None)
        h_raw = r.get("high", r.get("High"))
        l_raw = r.get("low", r.get("Low"))
        c_raw = r.get("close", r.get("Close"))
        # Validate before float — bool/gap must not compress into Wilder ATR.
        if not _valid_ohlc_bar(h_raw, l_raw, c_raw):
            return risk_reward_note(entry=entry or 0.0, atr=None)
        highs.append(float(h_raw))
        lows.append(float(l_raw))
        closes.append(float(c_raw))
    if not closes:
        return risk_reward_note(entry=entry or 0.0, atr=None)
    if entry is not None:
        if not _valid_close(entry):
            return risk_reward_note(entry=0.0, atr=None)
        px = float(entry)
    else:
        px = closes[-1]
    atr = average_true_range(highs, lows, closes, period=atr_period)
    swing = None
    if len(lows) >= 2:
        window = lows[-min(swing_lookback, len(lows)) :]
        swing = min(window) if window else None
    return risk_reward_note(entry=px, atr=atr, swing_low=swing)
