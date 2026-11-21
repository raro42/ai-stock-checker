"""BinanceFetcher strip limits must refuse bool invents."""

from __future__ import annotations

from stock_checker.binance_fetcher import (
    BINANCE_LIMIT_MAX,
    BINANCE_ORDERBOOK_LIMIT_MAX,
    DEFAULT_AGG_TRADES_LIMIT,
    DEFAULT_KLINES_EXTENDED_LIMIT,
    DEFAULT_KLINES_LIMIT,
    DEFAULT_ORDERBOOK_LIMIT,
    DEFAULT_RECENT_TRADES_LIMIT,
    _coerce_binance_limit,
)


def test_coerce_binance_limit_refuses_bool() -> None:
    """True→1 / min(True, 1000)→True must not invent a one-row strip."""
    assert _coerce_binance_limit(True, DEFAULT_KLINES_LIMIT) == DEFAULT_KLINES_LIMIT
    assert _coerce_binance_limit(False, DEFAULT_KLINES_LIMIT) == DEFAULT_KLINES_LIMIT
    assert _coerce_binance_limit(0, DEFAULT_KLINES_LIMIT) == DEFAULT_KLINES_LIMIT
    assert _coerce_binance_limit(None, DEFAULT_KLINES_LIMIT) == DEFAULT_KLINES_LIMIT
    assert _coerce_binance_limit(48, DEFAULT_KLINES_LIMIT) == 48


def test_coerce_binance_limit_caps_at_max() -> None:
    """Over-max falls to Binance ceiling (not uncapped)."""
    assert _coerce_binance_limit(5000, DEFAULT_KLINES_LIMIT) == BINANCE_LIMIT_MAX
    assert (
        _coerce_binance_limit(True, DEFAULT_RECENT_TRADES_LIMIT)
        == DEFAULT_RECENT_TRADES_LIMIT
    )
    assert (
        _coerce_binance_limit(True, DEFAULT_KLINES_EXTENDED_LIMIT)
        == DEFAULT_KLINES_EXTENDED_LIMIT
    )
    assert (
        _coerce_binance_limit(True, DEFAULT_AGG_TRADES_LIMIT)
        == DEFAULT_AGG_TRADES_LIMIT
    )


def test_coerce_orderbook_limit_refuses_bool() -> None:
    """True→1 must not invent a one-level orderbook depth strip."""
    assert (
        _coerce_binance_limit(
            True, DEFAULT_ORDERBOOK_LIMIT, ceiling=BINANCE_ORDERBOOK_LIMIT_MAX
        )
        == DEFAULT_ORDERBOOK_LIMIT
    )
    assert (
        _coerce_binance_limit(
            False, DEFAULT_ORDERBOOK_LIMIT, ceiling=BINANCE_ORDERBOOK_LIMIT_MAX
        )
        == DEFAULT_ORDERBOOK_LIMIT
    )
    assert (
        _coerce_binance_limit(
            100, DEFAULT_ORDERBOOK_LIMIT, ceiling=BINANCE_ORDERBOOK_LIMIT_MAX
        )
        == 100
    )
    assert (
        _coerce_binance_limit(
            9000, DEFAULT_ORDERBOOK_LIMIT, ceiling=BINANCE_ORDERBOOK_LIMIT_MAX
        )
        == BINANCE_ORDERBOOK_LIMIT_MAX
    )
