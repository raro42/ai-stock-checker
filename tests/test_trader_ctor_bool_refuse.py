"""IntelligentTrader constructor knobs must refuse bool invents."""

from __future__ import annotations

import math

from stock_checker.intelligent_trader import (
    IntelligentTrader,
    _DEFAULT_INITIAL_CASH,
    _DEFAULT_MAX_POSITIONS,
    _DEFAULT_MIN_HOLD_SECONDS,
    _DEFAULT_POSITION_SIZE,
    _DEFAULT_SCAN_INTERVAL_SEC,
    _DEFAULT_TRADE_INTERVAL_SEC,
    _coerce_trader_cash,
    _coerce_trader_frac,
    _coerce_trader_seconds,
    _coerce_trader_slots,
)


def test_trader_ctor_knobs_refuse_bool_invent() -> None:
    """tradermonty #700/#655 + xang1234/portfolio AI: True→1s / 100% / €1 refused."""
    assert _coerce_trader_seconds(True, _DEFAULT_SCAN_INTERVAL_SEC) == _DEFAULT_SCAN_INTERVAL_SEC
    assert _coerce_trader_seconds(False, _DEFAULT_TRADE_INTERVAL_SEC) == _DEFAULT_TRADE_INTERVAL_SEC
    assert _coerce_trader_seconds(math.nan, 900) == 900
    assert _coerce_trader_seconds(1800, 900) == 1800

    assert _coerce_trader_slots(True, _DEFAULT_MAX_POSITIONS) == _DEFAULT_MAX_POSITIONS
    assert _coerce_trader_slots(False, 1) == 1
    assert _coerce_trader_slots(5, 1) == 5

    assert _coerce_trader_frac(True, _DEFAULT_POSITION_SIZE) == _DEFAULT_POSITION_SIZE
    assert _coerce_trader_frac(False, _DEFAULT_POSITION_SIZE) == _DEFAULT_POSITION_SIZE
    assert _coerce_trader_frac(0.25, 0.10) == 0.25
    assert _coerce_trader_frac(1.5, 0.10) == 0.10  # >100% refuse

    assert _coerce_trader_cash(True) == _DEFAULT_INITIAL_CASH
    assert _coerce_trader_cash(False) == _DEFAULT_INITIAL_CASH
    assert _coerce_trader_cash(50_000) == 50_000.0

    assert _coerce_trader_seconds(True, _DEFAULT_MIN_HOLD_SECONDS) == _DEFAULT_MIN_HOLD_SECONDS


def test_post_stop_cooldown_refuses_bool_trade_interval() -> None:
    """True→1s trade interval must not invent a thin post-SL cooldown."""
    t = IntelligentTrader.__new__(IntelligentTrader)
    t.trade_interval = True  # type: ignore[assignment]
    assert t._post_stop_cooldown_seconds() == 14400.0
    t.trade_interval = False  # type: ignore[assignment]
    assert t._post_stop_cooldown_seconds() == 14400.0
    t.trade_interval = 20000
    assert t._post_stop_cooldown_seconds() == 20000.0
