"""Tests for paper exit / rotation policy."""

from stock_checker.exit_policy import (
    crypto_entry_price_ok,
    should_rebalance_exit,
    should_stop_loss,
    should_take_profit,
)


def test_take_profit_and_stop():
    assert should_take_profit(5.0)
    assert not should_take_profit(4.9)
    assert should_stop_loss(-5.0)
    assert not should_stop_loss(-4.9)


def test_never_rotate_losers():
    sell, why = should_rebalance_exit(
        profit_pct=-1.2,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell is False
    assert why == "no loss rotation"


def test_rotate_only_clear_winners_after_min_hold():
    sell, why = should_rebalance_exit(
        profit_pct=0.5,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell is False
    assert why == "below rotate hurdle"

    sell2, why2 = should_rebalance_exit(
        profit_pct=2.0,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell2 is True
    assert why2 == "rotate winner"

    held, why3 = should_rebalance_exit(
        profit_pct=5.0,
        hold_seconds=100,
        min_hold_seconds=14400,
    )
    assert held is False
    assert why3 == "min hold"


def test_crypto_price_floor():
    assert crypto_entry_price_ok(1.0)
    assert crypto_entry_price_ok(64000)
    assert not crypto_entry_price_ok(0.33)
    assert not crypto_entry_price_ok(0.09)
