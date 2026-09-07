from stock_checker.trade_postmortem import closed_rounds


def test_closed_rounds_pairs_buy_then_sell() -> None:
    trades = [
        {
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 2,
            "price": 100,
            "timestamp": "2026-09-01T10:00:00+00:00",
            "note": "Breakout near high",
            "strategy": "breakout",
            "score": 72,
        },
        {
            "type": "SELL",
            "symbol": "AAPL",
            "quantity": 2,
            "price": 108,
            "timestamp": "2026-09-02T10:00:00+00:00",
            "exit_reason": "tp",
            "note": "Profit target +8.0%",
        },
    ]
    rounds = closed_rounds(trades)
    assert len(rounds) == 1
    r = rounds[0]
    assert r["symbol"] == "AAPL"
    assert r["thesis"] == "Breakout near high"
    assert r["strategy"] == "breakout"
    assert r["exit_reason"] == "tp"
    assert r["exit_note"] == "Profit target +8.0%"
    assert r["held"] == "24h"
    assert r["profit_loss"] == 16.0
    assert r["profit_loss_pct"] == 8.0


def test_closed_rounds_fifo_partial_and_newest_first() -> None:
    trades = [
        {
            "type": "BUY",
            "symbol": "ETH",
            "quantity": 1,
            "price": 2000,
            "timestamp": "2026-09-01T00:00:00Z",
            "note": "First lot",
        },
        {
            "type": "BUY",
            "symbol": "ETH",
            "quantity": 1,
            "price": 2100,
            "timestamp": "2026-09-02T00:00:00Z",
            "note": "Second lot",
        },
        {
            "type": "SELL",
            "symbol": "ETH",
            "quantity": 1.5,
            "price": 2200,
            "timestamp": "2026-09-03T12:00:00Z",
            "exit_reason": "sl",
            "note": "Stop",
        },
    ]
    rounds = closed_rounds(trades)
    assert len(rounds) == 2
    # Newest-first: second slice (from lot 2) then first slice (from lot 1)
    assert rounds[0]["thesis"] == "Second lot"
    assert rounds[0]["quantity"] == 0.5
    assert rounds[1]["thesis"] == "First lot"
    assert rounds[1]["quantity"] == 1.0
    assert rounds[1]["exit_reason"] == "sl"


def test_closed_rounds_empty_and_open_only() -> None:
    assert closed_rounds([]) == []
    assert closed_rounds(
        [{"type": "BUY", "symbol": "BTC", "quantity": 0.1, "price": 50_000}]
    ) == []
