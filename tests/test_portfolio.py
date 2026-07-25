#!/usr/bin/env python3
"""Unit tests for portfolio fees and P&L (no network)."""

from stock_checker.portfolio import Portfolio


def test_buy_applies_commission_and_reduces_cash():
    p = Portfolio(initial_cash=10000.0, commission_rate=0.001, enable_risk_management=False)
    result = p.buy("AAPL", price=100.0, quantity=10, timestamp="2026-01-01")
    assert result["success"] is True
    # 1000 cost + 1 commission
    assert abs(p.cash - 8999.0) < 1e-6
    assert abs(p.total_fees_paid - 1.0) < 1e-6
    assert p.holdings["AAPL"] == 10


def test_sell_computes_pnl_and_fees():
    p = Portfolio(initial_cash=10000.0, commission_rate=0.001, enable_risk_management=False)
    p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    result = p.sell("AAPL", price=110.0, quantity=10, timestamp="t2")
    assert result["success"] is True
    tx = result["transaction"]
    assert abs(tx["profit_loss"] - 100.0) < 1e-6
    assert p.total_fees_paid > 1.0
    assert "AAPL" not in p.holdings


def test_insufficient_funds_fails():
    p = Portfolio(initial_cash=50.0, commission_rate=0.001, enable_risk_management=False)
    result = p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    assert result["success"] is False
