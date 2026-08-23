from stock_checker.portfolio import Portfolio


def test_buy_persists_context_fields() -> None:
    p = Portfolio(initial_cash=10000.0, persistence=None, enable_risk_management=False)
    result = p.buy(
        "AAPL",
        price=100.0,
        quantity=1,
        timestamp="2026-01-01",
        context={
            "strategy": "breakout",
            "note": "near 52w high",
            "score": 38.5,
            "confidence": "HIGH",
            "source": "scan",
        },
    )
    assert result["success"]
    tx = result["transaction"]
    assert tx["strategy"] == "breakout"
    assert tx["note"] == "near 52w high"
    assert tx["score"] == 38.5
    assert tx["confidence"] == "HIGH"
    assert tx["source"] == "scan"
