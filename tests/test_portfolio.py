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


def test_buy_sell_refuse_invalid_fill_marks():
    """tradermonty #655/#754: bool/gap/NaN must not invent €1 fills (float(True)→1.0)."""
    from stock_checker.portfolio import (
        INVALID_FILL_PRICE_REASON,
        fill_price_ok,
        long_only_quantity_ok,
    )

    p = Portfolio(
        initial_cash=10000.0,
        commission_rate=0.001,
        commission_min_eur=0.0,
        fee_preset="binance_like",
        enable_risk_management=False,
    )
    assert fill_price_ok(True) is False
    assert fill_price_ok(0) is False
    assert fill_price_ok(float("nan")) is False
    assert long_only_quantity_ok(True) is False
    assert p.can_buy("AAPL", True, 1) is False
    assert p.can_buy("AAPL", 100.0, True) is False

    bad_buy = p.buy("AAPL", price=True, quantity=1, timestamp="t1")
    assert bad_buy["success"] is False
    assert bad_buy["reason"] == INVALID_FILL_PRICE_REASON
    assert "AAPL" not in p.holdings

    ok = p.buy("AAPL", price=100.0, quantity=5, timestamp="t2")
    assert ok["success"] is True
    bad_sell = p.sell("AAPL", price=True, quantity=1, timestamp="t3")
    assert bad_sell["success"] is False
    assert bad_sell["reason"] == INVALID_FILL_PRICE_REASON
    assert p.holdings["AAPL"] == 5


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


def test_portfolio_load_refuses_bool_fee_schedule(tmp_path):
    """tradermonty #700/#655: True→100% / True→€1 must not invent ledger fees."""
    from stock_checker.persistence import DataPersistence

    persistence = DataPersistence(str(tmp_path))
    p = Portfolio(
        initial_cash=10_000.0,
        commission_rate=0.0025,
        commission_min_eur=1.0,
        fee_preset="revolut_standard",
        persistence=persistence,
        enable_risk_management=False,
    )
    p.buy("AAPL", price=100.0, quantity=1, timestamp="t1")
    state = persistence.load_portfolio()
    assert state is not None
    state["commission_rate"] = True
    state["commission_min_eur"] = True
    persistence.save_portfolio(state)

    reloaded = Portfolio(
        initial_cash=10_000.0,
        commission_rate=0.0025,
        commission_min_eur=1.0,
        fee_preset="revolut_standard",
        persistence=persistence,
        enable_risk_management=False,
    )
    assert abs(reloaded.commission_rate - 0.0025) < 1e-9
    assert abs(reloaded.commission_min_eur - 1.0) < 1e-9
    reloaded.set_fee_schedule(rate=True, min_eur=True, persist=False)
    assert abs(reloaded.commission_rate - 0.0025) < 1e-9
    assert abs(reloaded.commission_min_eur - 1.0) < 1e-9


def test_portfolio_ctor_refuses_bool_cash_and_fees():
    """True→€1 cash / True→100% rate / True→€1 min must not seed a new book."""
    from stock_checker.portfolio import (
        _DEFAULT_INITIAL_CASH,
        _coerce_portfolio_cash,
        _coerce_portfolio_fees_paid,
        _coerce_portfolio_min_eur,
        _coerce_portfolio_rate,
    )
    from stock_checker.fees import REVOLUT_STANDARD_MIN_EUR, REVOLUT_STANDARD_RATE

    assert _coerce_portfolio_cash(True) == _DEFAULT_INITIAL_CASH
    assert _coerce_portfolio_cash(False) == _DEFAULT_INITIAL_CASH
    assert _coerce_portfolio_cash(50_000) == 50_000.0
    assert _coerce_portfolio_cash(0) == 0.0
    assert _coerce_portfolio_rate(True, REVOLUT_STANDARD_RATE) == REVOLUT_STANDARD_RATE
    assert _coerce_portfolio_rate(0.001, REVOLUT_STANDARD_RATE) == 0.001
    assert _coerce_portfolio_min_eur(True, REVOLUT_STANDARD_MIN_EUR) == (
        REVOLUT_STANDARD_MIN_EUR
    )
    assert _coerce_portfolio_fees_paid(True) == 0.0
    assert _coerce_portfolio_fees_paid(12.5) == 12.5

    p = Portfolio(
        initial_cash=True,  # type: ignore[arg-type]
        commission_rate=True,  # type: ignore[arg-type]
        commission_min_eur=True,  # type: ignore[arg-type]
        enable_risk_management=False,
    )
    assert p.initial_cash == _DEFAULT_INITIAL_CASH
    assert p.cash == _DEFAULT_INITIAL_CASH
    assert abs(p.commission_rate - REVOLUT_STANDARD_RATE) < 1e-9
    assert abs(p.commission_min_eur - REVOLUT_STANDARD_MIN_EUR) < 1e-9


def test_portfolio_load_refuses_bool_cash_and_fees_paid(tmp_path):
    """Damaged ledger True→€1 cash / True→€1 fees must not invent book capital."""
    from stock_checker.persistence import DataPersistence
    from stock_checker.portfolio import _DEFAULT_INITIAL_CASH

    persistence = DataPersistence(str(tmp_path))
    p = Portfolio(
        initial_cash=10_000.0,
        commission_rate=0.0025,
        commission_min_eur=1.0,
        fee_preset="revolut_standard",
        persistence=persistence,
        enable_risk_management=False,
    )
    p.buy("AAPL", price=100.0, quantity=1, timestamp="t1")
    state = persistence.load_portfolio()
    assert state is not None
    state["initial_cash"] = True
    state["cash"] = True
    state["total_fees_paid"] = True
    persistence.save_portfolio(state)

    reloaded = Portfolio(
        initial_cash=10_000.0,
        commission_rate=0.0025,
        commission_min_eur=1.0,
        fee_preset="revolut_standard",
        persistence=persistence,
        enable_risk_management=False,
    )
    assert reloaded.initial_cash == _DEFAULT_INITIAL_CASH
    assert reloaded.cash == _DEFAULT_INITIAL_CASH
    assert reloaded.total_fees_paid == 0.0


def test_portfolio_mtm_refuses_bool_marks():
    """tradermonty #700/#655: True→€1 must not invent holdings MTM equity."""
    from stock_checker.portfolio import marked_lot_value

    assert marked_lot_value(True, 100.0) is None
    assert marked_lot_value(2, True) is None
    assert marked_lot_value(2, 50.0) == 100.0

    p = Portfolio(
        initial_cash=10_000.0,
        commission_rate=0.0,
        commission_min_eur=0.0,
        fee_preset="binance_like",
        enable_risk_management=False,
    )
    p.buy("AAPL", price=100.0, quantity=10, timestamp="t1")
    cash_after = p.cash
    # Bool mark falls back to cost (10×100), never invents 10×€1
    assert abs(p.get_portfolio_value({"AAPL": True}) - (cash_after + 1000.0)) < 1e-6
    assert abs(p.get_holdings_value({"AAPL": True}) - 1000.0) < 1e-6
    assert p.get_position("AAPL", True) is None
    # Real mark still marks to market
    assert abs(p.get_portfolio_value({"AAPL": 110.0}) - (cash_after + 1100.0)) < 1e-6
    pos = p.get_position("AAPL", 110.0)
    assert pos is not None
    assert abs(pos["profit_loss"] - 100.0) < 1e-6
