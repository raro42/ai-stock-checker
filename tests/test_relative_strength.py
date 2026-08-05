"""Offline tests for soft relative-strength entry gate."""

from stock_checker.relative_strength import (
    beats_benchmark,
    new_entry_rs_allowed,
    period_return,
    rs_gate_enabled,
    rs_lookback,
)


def _series(start: float, daily_ret: float, n: int) -> list[float]:
    out = [start]
    for _ in range(n - 1):
        out.append(out[-1] * (1.0 + daily_ret))
    return out


def test_period_return_needs_lookback_plus_one():
    assert period_return([1.0, 1.1], 5) is None
    closes = _series(100.0, 0.01, 10)
    ret = period_return(closes, 5)
    assert ret is not None
    # 5 steps of +1% ≈ (1.01**5)-1
    assert abs(ret - ((1.01**5) - 1.0)) < 1e-9


def test_beats_benchmark_allow_and_block():
    lookback = 10
    # Strong asset vs flat bench
    asset = _series(100.0, 0.02, lookback + 1)
    bench = _series(100.0, 0.0, lookback + 1)
    ok, why = beats_benchmark(asset, bench, lookback, asset_label="AAA", bench_label="SPY")
    assert ok
    assert "RS ok" in why

    weak = _series(100.0, -0.01, lookback + 1)
    blocked, why_b = beats_benchmark(
        weak, bench, lookback, asset_label="ZZZ", bench_label="SPY"
    )
    assert not blocked
    assert "lagging" in why_b


def test_beats_benchmark_fail_open_short_history():
    ok, why = beats_benchmark([1.0, 2.0], [1.0, 1.1], 63)
    assert ok
    assert "unknown" in why


def test_new_entry_rs_allowed_stock_and_crypto():
    lb = 10
    spy = _series(100.0, 0.005, lb + 1)
    strong = _series(50.0, 0.02, lb + 1)
    weak = _series(50.0, -0.01, lb + 1)
    btc = _series(40000.0, 0.01, lb + 1)

    ok, _ = new_entry_rs_allowed(
        symbol="AAPL",
        is_crypto=False,
        asset_closes=strong,
        spy_closes=spy,
        btc_closes=btc,
        lookback=lb,
        enabled=True,
    )
    assert ok

    blocked, why = new_entry_rs_allowed(
        symbol="LAGGARD",
        is_crypto=False,
        asset_closes=weak,
        spy_closes=spy,
        btc_closes=btc,
        lookback=lb,
        enabled=True,
    )
    assert not blocked
    assert "SPY" in why

    # Benchmark symbols always pass
    ok_spy, _ = new_entry_rs_allowed(
        symbol="SPY",
        is_crypto=False,
        asset_closes=weak,
        spy_closes=spy,
        btc_closes=btc,
        lookback=lb,
        enabled=True,
    )
    assert ok_spy

    # Gate off
    ok_off, _ = new_entry_rs_allowed(
        symbol="LAGGARD",
        is_crypto=False,
        asset_closes=weak,
        spy_closes=spy,
        btc_closes=btc,
        lookback=lb,
        enabled=False,
    )
    assert ok_off

    # Crypto lagging BTC
    weak_crypto = _series(100.0, -0.02, lb + 1)
    blocked_c, why_c = new_entry_rs_allowed(
        symbol="DOGE-USD",
        is_crypto=True,
        asset_closes=weak_crypto,
        spy_closes=spy,
        btc_closes=btc,
        lookback=lb,
        enabled=True,
    )
    assert not blocked_c
    assert "BTC" in why_c


def test_rs_gate_env(monkeypatch):
    monkeypatch.setenv("RS_GATE", "0")
    assert rs_gate_enabled() is False
    monkeypatch.setenv("RS_GATE", "1")
    assert rs_gate_enabled() is True
    monkeypatch.setenv("RS_LOOKBACK", "30")
    assert rs_lookback() == 30
    monkeypatch.setenv("RS_LOOKBACK", "9999")
    assert rs_lookback() == 252
