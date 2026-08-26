from stock_checker.portfolio import Portfolio
from stock_checker.trade_context import sell_note_from_exit


def test_sell_persists_context_fields() -> None:
    p = Portfolio(initial_cash=10000.0, persistence=None, enable_risk_management=False)
    p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    result = p.sell(
        "AAPL",
        price=90.0,
        quantity=10,
        timestamp="t2",
        context=sell_note_from_exit(
            exit_reason="sl", profit_pct=-10.0, threshold=5.0
        ),
    )
    assert result["success"]
    tx = result["transaction"]
    assert tx["exit_reason"] == "sl"
    assert "Stop loss" in tx["note"]
