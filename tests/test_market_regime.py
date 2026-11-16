"""Offline tests for SMA market-regime gate."""

from stock_checker.market_regime import (
    CRYPTO_BENCHMARK,
    CRYPTO_BENCHMARK_IDENTITY,
    CRYPTO_BENCHMARK_KIND,
    CRYPTO_BENCHMARK_NOT,
    REGIME_OFF,
    REGIME_ON,
    REGIME_UNKNOWN,
    STOCK_BENCHMARK,
    STOCK_BENCHMARK_IDENTITY,
    STOCK_BENCHMARK_KIND,
    STOCK_BENCHMARK_NOT,
    classify_close_vs_sma,
    closes_from_binance_klines,
    closes_from_yfinance_hist,
    crypto_benchmark_identity,
    new_entry_allowed,
    regime_analogue_label,
    simple_sma,
    snapshot_dict,
    stock_benchmark_identity,
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


def test_regime_analogue_rejects_weak_or_incomplete():
    # Far enough from the average to name the heuristic sleeve.
    assert regime_analogue_label(REGIME_ON, 110.0, 100.0) == "risk_on · heuristic"
    assert regime_analogue_label(REGIME_OFF, 90.0, 100.0) == "risk_off · heuristic"
    # Hugging the SMA is not a comparable episode.
    assert regime_analogue_label(REGIME_ON, 100.2, 100.0) == "near SMA"
    assert regime_analogue_label(REGIME_OFF, 99.6, 100.0) == "near SMA"
    # Named regime without prices cannot be checked — refuse the claim.
    assert regime_analogue_label(REGIME_ON, None, 100.0) == "no analogue"
    assert regime_analogue_label(REGIME_OFF, 100.0, None) == "no analogue"
    assert regime_analogue_label(REGIME_UNKNOWN, 110.0, 100.0) == REGIME_UNKNOWN
    assert regime_analogue_label("", None, None) == "—"
    # Gate reason strings stay the binary close-vs-SMA rule.
    blocked, why = new_entry_allowed(
        is_crypto=False,
        stock_regime=REGIME_OFF,
        crypto_regime=REGIME_ON,
        enabled=True,
    )
    assert not blocked
    assert why == "SPY risk-off (below SMA)"
    snap = snapshot_dict(stock_regime=REGIME_ON, crypto_regime=REGIME_OFF)
    assert snap["score_kind"] == "heuristic_sma"
    assert snap["calibrated_probability"] is False
    assert snap["stock_benchmark"] == STOCK_BENCHMARK
    assert snap["stock_benchmark_kind"] == STOCK_BENCHMARK_KIND
    assert snap["stock_benchmark_not"] == STOCK_BENCHMARK_NOT
    assert snap["stock_benchmark_identity"] == STOCK_BENCHMARK_IDENTITY
    assert snap["crypto_benchmark"] == CRYPTO_BENCHMARK
    assert snap["crypto_benchmark_kind"] == CRYPTO_BENCHMARK_KIND
    assert snap["crypto_benchmark_not"] == CRYPTO_BENCHMARK_NOT
    assert snap["crypto_benchmark_identity"] == CRYPTO_BENCHMARK_IDENTITY
    assert snap["crypto_benchmark"] != "BTC-USD"


def test_stock_benchmark_identity_etf_proxy_not_index():
    """tradermonty #765: SPY is an ETF proxy, not ^GSPC (display only)."""
    ident = stock_benchmark_identity()
    assert ident["symbol"] == "SPY"
    assert ident["kind"] == "etf_proxy"
    assert ident["not_index"] == "^GSPC"
    assert ident["bit"] == STOCK_BENCHMARK_IDENTITY
    assert "ETF proxy" in ident["bit"]
    assert "^GSPC" in ident["bit"]


def test_crypto_benchmark_identity_binance_pair_not_yahoo():
    """tradermonty #765/#766: BTCUSDT is Binance, not Yahoo BTC-USD."""
    ident = crypto_benchmark_identity()
    assert ident["symbol"] == "BTCUSDT"
    assert ident["kind"] == "binance_pair"
    assert ident["not_yahoo"] == "BTC-USD"
    assert ident["bit"] == CRYPTO_BENCHMARK_IDENTITY
    assert "Binance" in ident["bit"]
    assert "BTC-USD" in ident["bit"]


def test_nan_closes_fail_open_as_unknown():
    assert classify_close_vs_sma([float("nan")] * 60, 50) == REGIME_UNKNOWN
    # Gap in the SMA window is unknown — do not strip NaN and score risk_off
    # (xang1234 / portfolio AI claim honesty after silent shorten)
    series = [100.0] * 49 + [float("nan"), 50.0]
    assert classify_close_vs_sma(series, 50) == REGIME_UNKNOWN
    assert simple_sma(series, 50) is None


def test_zero_or_negative_close_fail_open_as_unknown():
    """tradermonty #655/#754: zero/neg close ≠ a real regime episode."""
    assert classify_close_vs_sma([100.0] * 49 + [0.0], 50) == REGIME_UNKNOWN
    assert classify_close_vs_sma([100.0] * 49 + [-1.0], 50) == REGIME_UNKNOWN
    assert simple_sma([100.0] * 49 + [0.0], 50) is None

