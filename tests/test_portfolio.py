#!/usr/bin/env python3
"""Unit tests for portfolio fees and P&L (no network)."""

from stock_checker.portfolio import Portfolio


def test_buy_applies_commission_and_reduces_cash():
    p = Portfolio(initial_cash=10000.0, commission_rate=0.001, commission_min_eur=0.0, enable_risk_management=False)
    result = p.buy("AAPL", price=100.0, quantity=10, timestamp="2026-01-01")
    assert result["success"] is True
    # 1000 cost + 1 commission
    assert abs(p.cash - 8999.0) < 1e-6
    assert abs(p.total_fees_paid - 1.0) < 1e-6
    assert p.holdings["AAPL"] == 10


def test_sell_computes_pnl_and_fees():
    p = Portfolio(initial_cash=10000.0, commission_rate=0.001, commission_min_eur=0.0, enable_risk_management=False)
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


def test_revolut_min_commission_floor():
    from stock_checker.fees import REVOLUT_STANDARD_MIN_EUR, REVOLUT_STANDARD_RATE

    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=REVOLUT_STANDARD_RATE,
        commission_min_eur=REVOLUT_STANDARD_MIN_EUR,
        enable_risk_management=False,
    )
    # €400 notional × 0.25% = €1.00 exactly at the floor edge
    result = p.buy("AAPL", price=40.0, quantity=10, timestamp="t1")
    assert result["success"] is True
    assert abs(result["transaction"]["commission"] - 1.0) < 1e-6
    # Small notional still pays €1 min
    p2 = Portfolio(
        initial_cash=10000.0,
        commission_rate=REVOLUT_STANDARD_RATE,
        commission_min_eur=REVOLUT_STANDARD_MIN_EUR,
        enable_risk_management=False,
    )
    small = p2.buy("AAPL", price=10.0, quantity=5, timestamp="t1")  # €50 → min €1
    assert abs(small["transaction"]["commission"] - 1.0) < 1e-6
