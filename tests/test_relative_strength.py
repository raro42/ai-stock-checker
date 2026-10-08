"""Offline tests for soft relative-strength entry gate."""

from stock_checker.relative_strength import (
    RS_ANCHOR_MAX_MISS,
    anchor_miss_ratio,
    beats_benchmark,
    new_entry_rs_allowed,
    period_return,
    rs_anchor_max_miss,
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
    assert "anchor gap" not in why


def test_anchor_miss_ratio_positional():
    lb = 5
    clean = _series(100.0, 0.01, lb + 1)
    assert anchor_miss_ratio(clean, lb) == 0.0
    assert anchor_miss_ratio(clean[:3], lb) is None
    gappy = list(clean)
    gappy[2] = float("nan")
    gappy[3] = float("nan")
    # 2/6 ≈ 0.333 > 0.25
    assert anchor_miss_ratio(gappy, lb) == 2 / float(lb + 1)


def test_period_return_rejects_heavy_anchor_gap():
    lb = 5
    closes = _series(100.0, 0.01, lb + 1)
    # Steal older bars via NaN-drop used to invent a return; positional miss
    # above the 25% floor must refuse.
    padded = [90.0, 91.0, 92.0] + list(closes)
    padded[-4] = float("nan")
    padded[-3] = float("nan")
    assert len(padded) >= lb + 1
    window = padded[-(lb + 1) :]
    miss = sum(1 for c in window if c != c) / float(lb + 1)
    assert miss > RS_ANCHOR_MAX_MISS
    assert period_return(padded, lb) is None


def test_period_return_tolerates_light_interior_hole():
    lb = 5
    closes = _series(100.0, 0.01, lb + 1)
    closes[2] = float("nan")  # 1/6 ≤ 0.25; start+end finite
    ret = period_return(closes, lb)
    assert ret is not None
    assert abs(ret - (closes[-1] / closes[0] - 1.0)) < 1e-9


def test_beats_benchmark_fail_open_anchor_gap():
    lb = 5
    bench = _series(100.0, 0.0, lb + 1)
    # Asset window: 2 NaNs → miss >25% → fail-open, never a lagging block.
    asset = _series(100.0, -0.02, lb + 1)
    asset[1] = float("nan")
    asset[2] = float("nan")
    ok, why = beats_benchmark(
        asset, bench, lb, asset_label="HOLE", bench_label="SPY"
    )
    assert ok
    assert "anchor gap" in why
    assert "lagging" not in why

    # Benchmark holes fail-open the same way (do not invent SPY RS).
    spy_hole = list(bench)
    spy_hole[1] = float("nan")
    spy_hole[2] = float("nan")
    strong = _series(50.0, 0.02, lb + 1)
    ok_b, why_b = beats_benchmark(
        strong, spy_hole, lb, asset_label="AAA", bench_label="SPY"
    )
    assert ok_b
    assert "SPY" in why_b
    assert "anchor gap" in why_b


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


def test_rs_anchor_max_miss_env_clamp(monkeypatch):
    """xang1234 #539 30c6c2d: bad/out-of-range override falls back to default."""
    monkeypatch.delenv("RS_ANCHOR_MAX_MISS", raising=False)
    assert rs_anchor_max_miss() == RS_ANCHOR_MAX_MISS
    monkeypatch.setenv("RS_ANCHOR_MAX_MISS", "0.4")
    assert rs_anchor_max_miss() == 0.4
    monkeypatch.setenv("RS_ANCHOR_MAX_MISS", "0")
    assert rs_anchor_max_miss() == 0.0
    monkeypatch.setenv("RS_ANCHOR_MAX_MISS", "1")
    assert rs_anchor_max_miss() == 1.0
    for raw in ("50%", "nan", "inf", "-0.1", "1.5", "nope"):
        monkeypatch.setenv("RS_ANCHOR_MAX_MISS", raw)
        assert rs_anchor_max_miss() == RS_ANCHOR_MAX_MISS
