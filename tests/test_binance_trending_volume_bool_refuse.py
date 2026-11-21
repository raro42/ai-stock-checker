"""Binance trending top_n + min-volume floor must refuse bool invents."""

from __future__ import annotations

from stock_checker.binance_fetcher import (
    DEFAULT_MIN_VOLUME_USDT,
    DEFAULT_TRENDING_TOP_N,
    BinanceFetcher,
    _coerce_binance_limit,
    _coerce_binance_min_volume,
)


def test_coerce_binance_min_volume_refuses_bool() -> None:
    """True→$1 / False→$0 must not invent a cleared liquidity floor."""
    assert _coerce_binance_min_volume(True) == DEFAULT_MIN_VOLUME_USDT
    assert _coerce_binance_min_volume(False) == DEFAULT_MIN_VOLUME_USDT
    assert _coerce_binance_min_volume(0) == DEFAULT_MIN_VOLUME_USDT
    assert _coerce_binance_min_volume(None) == DEFAULT_MIN_VOLUME_USDT
    assert _coerce_binance_min_volume(-1) == DEFAULT_MIN_VOLUME_USDT
    assert _coerce_binance_min_volume(25_000_000) == 25_000_000.0


def test_coerce_trending_top_n_refuses_bool() -> None:
    """True→1 / [:True] must not invent a one-coin trending strip."""
    assert (
        _coerce_binance_limit(True, DEFAULT_TRENDING_TOP_N) == DEFAULT_TRENDING_TOP_N
    )
    assert (
        _coerce_binance_limit(False, DEFAULT_TRENDING_TOP_N) == DEFAULT_TRENDING_TOP_N
    )
    assert _coerce_binance_limit(0, DEFAULT_TRENDING_TOP_N) == DEFAULT_TRENDING_TOP_N
    assert _coerce_binance_limit(48, DEFAULT_TRENDING_TOP_N) == 48


def test_get_trending_coins_bool_top_n_falls_back(monkeypatch) -> None:
    """Damaged top_n=True must not slice trending to a one-row strip."""
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            rows = []
            for i in range(30):
                rows.append(
                    {
                        "symbol": f"COIN{i}USDT",
                        "quoteVolume": str(50_000_000 + i),
                        "count": 1000 + i,
                        "priceChangePercent": str(1.0 + i * 0.1),
                        "lastPrice": "1.0",
                        "highPrice": "1.1",
                        "lowPrice": "0.9",
                    }
                )
            return rows

    monkeypatch.setattr(
        fetcher.session,
        "get",
        lambda *a, **k: _Resp(),
    )
    out = fetcher.get_trending_coins(top_n=True, min_volume_usdt=True)
    assert len(out) == DEFAULT_TRENDING_TOP_N


def test_get_all_tickers_bool_min_volume_falls_back(monkeypatch) -> None:
    """Damaged min_volume=True must keep the $10M floor (not $1)."""
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {
                    "symbol": "LOWUSDT",
                    "quoteVolume": "100",  # below default floor
                    "lastPrice": "1.0",
                    "priceChangePercent": "1.0",
                    "highPrice": "1.1",
                    "lowPrice": "0.9",
                    "volume": "100",
                    "count": 10,
                    "closeTime": 1,
                },
                {
                    "symbol": "HIUSDT",
                    "quoteVolume": str(DEFAULT_MIN_VOLUME_USDT + 1),
                    "lastPrice": "2.0",
                    "priceChangePercent": "2.0",
                    "highPrice": "2.1",
                    "lowPrice": "1.9",
                    "volume": "200",
                    "count": 20,
                    "closeTime": 2,
                },
            ]

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_all_tickers(min_volume_usdt=True)
    assert "LOWUSDT" not in out
    assert "HIUSDT" in out
