#!/usr/bin/env python3
"""Unit tests for portfolio fees and P&L (no network)."""

from stock_checker.portfolio import Portfolio


def test_buy_applies_commission_and_reduces_cash():
    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=0.001,
        commission_min_eur=0.0,
        fee_preset="binance_like",
        enable_risk_management=False,
    )
    result = p.buy("AAPL", price=100.0, quantity=10, timestamp="2026-01-01")
    assert result["success"] is True
    # 1000 cost + 1 commission
    assert abs(p.cash - 8999.0) < 1e-6
    assert abs(p.total_fees_paid - 1.0) < 1e-6
    assert p.holdings["AAPL"] == 10


def test_sell_computes_pnl_and_fees():
    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=0.001,
        commission_min_eur=0.0,
        fee_preset="binance_like",
        enable_risk_management=False,
    )
    p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    result = p.sell("AAPL", price=110.0, quantity=10, timestamp="t2")
    assert result["success"] is True
    tx = result["transaction"]
    assert abs(tx["profit_loss"] - 100.0) < 1e-6
    assert p.total_fees_paid > 1.0
    assert "AAPL" not in p.holdings


def test_insufficient_funds_fails():
    p = Portfolio(initial_cash=50.0, commission_rate=0.001, commission_min_eur=0.0, enable_risk_management=False)
    result = p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    assert result["success"] is False


def test_can_buy_with_cash_and_refuses_short():
    """tradermonty #681: long-only — can_buy must not NameError; shorts refuse."""
    from stock_checker.portfolio import UNSUPPORTED_SHORT_REASON, long_only_quantity_ok

    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=0.001,
        commission_min_eur=0.0,
        fee_preset="binance_like",
        enable_risk_management=False,
    )
    assert p.can_buy("AAPL", 100.0, 1) is True
    assert p.can_buy("AAPL", 100.0, 0) is False
    assert p.can_buy("AAPL", 100.0, -1) is False
    assert long_only_quantity_ok(-1) is False
    buy = p.buy("AAPL", price=100.0, quantity=-2, timestamp="t1")
    assert buy["success"] is False
    assert buy["reason"] == UNSUPPORTED_SHORT_REASON
    p.buy("AAPL", price=100.0, quantity=5, timestamp="t2")
    sell = p.sell("AAPL", price=100.0, quantity=-1, timestamp="t3")
    assert sell["success"] is False
    assert sell["reason"] == UNSUPPORTED_SHORT_REASON
    # Selling more than held is insufficient shares — not a short open.
    over = p.sell("AAPL", price=100.0, quantity=99, timestamp="t4")
    assert over["success"] is False
    assert over["reason"] == "Insufficient shares"


def test_revolut_min_commission_floor():
    from stock_checker.fees import REVOLUT_STANDARD_MIN_EUR, REVOLUT_STANDARD_RATE

    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=REVOLUT_STANDARD_RATE,
        commission_min_eur=REVOLUT_STANDARD_MIN_EUR,
        fee_preset="revolut_standard",
        enable_risk_management=False,
    )
    # First leg in month is free (Standard allowance = 1)
    result = p.buy("AAPL", price=40.0, quantity=10, timestamp="2026-08-01 10:00:00")
    assert result["success"] is True
    assert abs(result["transaction"]["commission"] - 0.0) < 1e-6
    # Second leg pays €1 min on small notional
    small = p.buy("MSFT", price=10.0, quantity=5, timestamp="2026-08-01 11:00:00")
    assert abs(small["transaction"]["commission"] - 1.0) < 1e-6
