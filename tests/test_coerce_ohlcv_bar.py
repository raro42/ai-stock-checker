"""Offline tests for OHLCV bar coerce (overnight / CLI Yahoo loaders)."""

from stock_checker.technical_indicators import coerce_ohlcv_bar


def test_coerce_ohlcv_bar_ok():
    bar = coerce_ohlcv_bar(
        open_=10.0, high=11.0, low=9.5, close=10.5, volume=1_000.0, date="d"
    )
    assert bar == {
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": 10.5,
        "volume": 1000.0,
        "date": "d",
    }


def test_coerce_ohlcv_bar_missing_volume_is_zero():
    bar = coerce_ohlcv_bar(open_=10.0, high=10.0, low=10.0, close=10.0)
    assert bar is not None
    assert bar["volume"] == 0.0


def test_coerce_ohlcv_bar_refuses_bool_ohlc():
    """True→$1 must not invent an overnight / CLI fill print."""
    assert (
        coerce_ohlcv_bar(open_=True, high=11.0, low=9.0, close=10.0, volume=1.0)
        is None
    )
    assert (
        coerce_ohlcv_bar(open_=10.0, high=True, low=9.0, close=10.0, volume=1.0)
        is None
    )
    assert (
        coerce_ohlcv_bar(open_=10.0, high=11.0, low=9.0, close=True, volume=1.0)
        is None
    )


def test_coerce_ohlcv_bar_refuses_bool_volume():
    """True→1 volume must not invent a volume-confirm bar."""
    assert (
        coerce_ohlcv_bar(open_=10.0, high=11.0, low=9.0, close=10.0, volume=True)
        is None
    )


def test_coerce_ohlcv_bar_refuses_inverted():
    assert (
        coerce_ohlcv_bar(open_=10.0, high=9.0, low=11.0, close=10.0, volume=0.0)
        is None
    )
    assert (
        coerce_ohlcv_bar(open_=10.0, high=11.0, low=9.0, close=12.0, volume=0.0)
        is None
    )
