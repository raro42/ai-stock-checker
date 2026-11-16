"""Offline: overnight experiment_strategy refuses bool/gap/NaN closes."""

from __future__ import annotations

from stock_checker.experiment_strategy import (
    MED_SMA,
    _closes_until,
    _vols_until,
    generate_signals,
)


def _bars(n: int, *, start: float = 100.0, step: float = 0.5) -> list[dict]:
    out = []
    for i in range(n):
        close = start + i * step
        out.append(
            {
                "close": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "open": close,
                "volume": 1_000_000 + i * 1000,
            }
        )
    return out


def test_closes_until_refuses_bool_and_nan():
    bars = _bars(5)
    bars[2]["close"] = True  # float(True) == 1.0 trap
    assert _closes_until(bars, index=4) is None
    bars[2]["close"] = 101.0
    bars[3]["close"] = float("nan")
    assert _closes_until(bars, index=4) is None
    bars[3]["close"] = 102.0
    assert _closes_until(bars, index=4) is not None


def test_vols_until_refuses_bool_and_negative():
    bars = _bars(5)
    bars[1]["volume"] = True
    assert _vols_until(bars, index=4) is None
    bars[1]["volume"] = 1_000_000
    bars[2]["volume"] = -1
    assert _vols_until(bars, index=4) is None
    bars[2]["volume"] = 0
    assert _vols_until(bars, index=4) is not None


def test_generate_signals_skips_gap_close():
    n = MED_SMA + 5
    bars = _bars(n)
    bars[-2]["close"] = float("nan")
    signals = generate_signals(
        {"AAA": bars},
        index=n - 1,
        portfolio={"positions": {}},
    )
    assert "AAA" not in signals


def test_generate_signals_skips_bool_close():
    n = MED_SMA + 5
    bars = _bars(n)
    bars[-1]["close"] = True
    signals = generate_signals(
        {"AAA": bars},
        index=n - 1,
        portfolio={"positions": {"AAA": {"qty": 1}}},
    )
    assert "AAA" not in signals
