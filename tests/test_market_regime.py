"""Offline tests for SMA market-regime gate."""

from stock_checker.market_regime import (
    REGIME_OFF,
    REGIME_ON,
    REGIME_UNKNOWN,
    classify_close_vs_sma,
    closes_from_binance_klines,
    closes_from_yfinance_hist,
    new_entry_allowed,
    simple_sma,
)


def test_simple_sma_needs_full_window():
    assert simple_sma([1, 2, 3], 5) is None
    assert simple_sma([1, 2, 3, 4, 5], 5) == 3.0


def test_classify_risk_on_off():
    # Rising series ending above SMA
    up = [float(i) for i in range(1, 61)]
    assert classify_close_vs_sma(up, 50) == REGIME_ON
    # Flat then dump below SMA
    dump = [100.0] * 49 + [50.0]
    assert classify_close_vs_sma(dump, 50) == REGIME_OFF
    assert classify_close_vs_sma([1.0, 2.0], 50) == REGIME_UNKNOWN


def test_new_entry_allowed_fail_open_and_block():
    ok, _ = new_entry_allowed(
        is_crypto=False,
        stock_regime=REGIME_ON,
        crypto_regime=REGIME_OFF,
        enabled=True,
    )
    assert ok

    blocked, why = new_entry_allowed(
        is_crypto=False,
        stock_regime=REGIME_OFF,
        crypto_regime=REGIME_ON,
        enabled=True,
    )
    assert not blocked
    assert "SPY" in why

    blocked_c, why_c = new_entry_allowed(
        is_crypto=True,
        stock_regime=REGIME_ON,
        crypto_regime=REGIME_OFF,
        enabled=True,
    )
    assert not blocked_c
    assert "BTC" in why_c

    # Fail open on unknown
    ok_u, _ = new_entry_allowed(
        is_crypto=True,
        stock_regime=REGIME_OFF,
        crypto_regime=REGIME_UNKNOWN,
        enabled=True,
    )
    assert ok_u

    # Gate off always allows
    ok_off, _ = new_entry_allowed(
        is_crypto=False,
        stock_regime=REGIME_OFF,
        crypto_regime=REGIME_OFF,
        enabled=False,
    )
    assert ok_off


def test_close_extractors():
    hist = {
        "data": {
            "2024-01-02": {"Close": 10.0},
            "2024-01-01": {"Close": 9.0},
        }
    }
    assert closes_from_yfinance_hist(hist) == [9.0, 10.0]
    klines = [{"close": 1}, {"close": "2.5"}, {"close": "x"}]
    assert closes_from_binance_klines(klines) == [1.0, 2.5]


def test_nan_closes_fail_open_as_unknown():
    assert classify_close_vs_sma([float("nan")] * 60, 50) == REGIME_UNKNOWN
    # Trailing NaN stripped; last finite close below SMA → risk_off
    series = [100.0] * 49 + [float("nan"), 50.0]
    assert classify_close_vs_sma(series, 50) == REGIME_OFF

