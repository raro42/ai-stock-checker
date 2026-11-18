"""Offline tests for promoted champion entry filter."""

import math
from datetime import datetime, timedelta

from stock_checker.promoted_strategy import (
    bars_from_closes,
    champion_wants_buy,
    filter_opportunities,
)


def _rising(n: int = 120, start: float = 100.0) -> list[float]:
    out = []
    px = start
    for _ in range(n):
        px *= 1.008
        out.append(px)
    return out


def _falling(n: int = 120, start: float = 100.0) -> list[float]:
    out = []
    px = start
    for _ in range(n):
        px *= 0.995
        out.append(px)
    return out


def test_bars_from_closes_length():
    bars = bars_from_closes([1.0, 2.0, 3.0], start=datetime(2024, 1, 1))
    assert len(bars) == 3
    assert bars[0]["date"] == datetime(2024, 1, 1)
    assert bars[2]["date"] == datetime(2024, 1, 1) + timedelta(days=2)


def test_bars_from_closes_refuses_invalid():
    """tradermonty #655/#754: bool/gap/NaN cannot invent champion bars (True→1.0)."""
    bars = bars_from_closes(
        [10.0, True, 0, -1, math.nan, None, "12.5", 11.0],  # type: ignore[list-item]
        start=datetime(2024, 1, 1),
        volumes=[1e6, True, 1e6, 1e6, 1e6, 1e6, 1e6, -5],  # type: ignore[list-item]
    )
    assert len(bars) == 2
    assert bars[0]["close"] == 10.0
    assert bars[1]["close"] == 11.0
    assert bars[0]["volume"] == 1_000_000.0
    # invalid volume on the valid close falls back to default (no True→1 invent)
    assert bars[1]["volume"] == 1_000_000.0
    assert bars[1]["date"] == datetime(2024, 1, 2)


def test_filter_rejects_when_signal_fn_says_no():
    def never_buy(bars_by_symbol, index, portfolio):
        return {}

    bars = {"AAA": bars_from_closes(_rising()), "SPY": bars_from_closes(_rising())}
    opps = [{"symbol": "AAA", "score": 10.0, "rank": 1}]
    kept = filter_opportunities(opps, bars, signal_fn=never_buy)
    assert kept == []


def test_filter_keeps_when_signal_fn_buys():
    def always_buy(bars_by_symbol, index, portfolio):
        return {s: "BUY" for s in bars_by_symbol if s != "SPY"}

    bars = {"AAA": bars_from_closes(_rising()), "SPY": bars_from_closes(_rising())}
    opps = [{"symbol": "AAA", "score": 10.0, "rank": 1}]
    kept = filter_opportunities(opps, bars, signal_fn=always_buy)
    assert len(kept) == 1
    assert kept[0]["promoted_filter"] == "buy"
    assert kept[0]["score"] > 10.0


def test_filter_keeps_when_no_bars():
    opps = [{"symbol": "ZZZ", "score": 5.0, "rank": 1}]
    kept = filter_opportunities(opps, {}, signal_fn=lambda *a, **k: {})
    assert len(kept) == 1
    assert kept[0]["promoted_filter"] == "skip_no_bars"


def test_promote_ignores_champion_sell_for_entry_filter():
    """Contract: promote is entry BUY filter only — SELL signals do not pass as buys."""

    def only_sell(bars_by_symbol, index, portfolio):
        return {s: "SELL" for s in bars_by_symbol if s != "SPY"}

    bars = {"AAA": bars_from_closes(_rising()), "SPY": bars_from_closes(_rising())}
    opps = [{"symbol": "AAA", "score": 10.0, "rank": 1}]
    kept = filter_opportunities(opps, bars, signal_fn=only_sell)
    assert kept == []


def test_champion_wants_buy_none_on_short_series():
    bars = {"AAA": bars_from_closes([1.0, 2.0, 3.0])}
    assert champion_wants_buy(bars, "AAA") is None


def test_filter_refuses_invalid_score_boost_and_rank():
    """tradermonty #700/#655: bool/gap scores cannot invent True→1.0 boost/rank."""

    def always_buy(bars_by_symbol, index, portfolio):
        return {s: "BUY" for s in bars_by_symbol if s != "SPY"}

    bars = {
        "AAA": bars_from_closes(_rising()),
        "BBB": bars_from_closes(_rising()),
        "SPY": bars_from_closes(_rising()),
    }
    opps = [
        {"symbol": "AAA", "score": True, "rank": 1},
        {"symbol": "BBB", "score": 20.0, "rank": 2},
    ]
    kept = filter_opportunities(opps, bars, signal_fn=always_buy)
    assert len(kept) == 2
    by_sym = {row["symbol"]: row for row in kept}
    # bool score refused — no invent boost; stays True (unreadable)
    assert by_sym["AAA"]["score"] is True
    assert by_sym["BBB"]["score"] == 20.0 * 1.15
    # readable score ranks first even when bool would have sorted as 1.0
    assert kept[0]["symbol"] == "BBB"
    assert kept[1]["symbol"] == "AAA"
