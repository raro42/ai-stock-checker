"""Tests for paper exit / rotation policy."""

from stock_checker.exit_policy import (
    book_action_mode,
    crypto_entry_price_ok,
    opportunity_symbol_set,
    should_allow_rebuy,
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
    # SCHW-style +1.6% must NOT rotate under Revolut fees
    sell_thin, why_thin = should_rebalance_exit(
        profit_pct=1.63,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell_thin is False
    assert why_thin == "below rotate hurdle"

    sell, why = should_rebalance_exit(
        profit_pct=0.5,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell is False
    assert why == "below rotate hurdle"

    sell2, why2 = should_rebalance_exit(
        profit_pct=3.0,
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


def test_rebuy_cooldown_blocks_flip_flop():
    ok, why = should_allow_rebuy(seconds_since_exit=None, cooldown_seconds=86400)
    assert ok is True
    blocked, why_b = should_allow_rebuy(seconds_since_exit=600, cooldown_seconds=86400)
    assert blocked is False
    assert why_b == "rebuy cooldown"
    clear, why_c = should_allow_rebuy(seconds_since_exit=90000, cooldown_seconds=86400)
    assert clear is True
    assert why_c == "cooldown clear"


def test_opportunity_symbol_set_includes_beyond_top_n():
    opps = [{"symbol": "A"}, {"symbol": "SCHW"}, {"symbol": "B"}]
    assert opportunity_symbol_set(opps) == {"A", "SCHW", "B"}
    assert opportunity_symbol_set([]) == set()


def test_book_action_mode():
    assert book_action_mode(3, 5) == "open"
    assert book_action_mode(5, 5) == "at_cap"
    assert book_action_mode(9, 5) == "overweight"


def test_crypto_price_floor():
    assert crypto_entry_price_ok(1.0)
    assert crypto_entry_price_ok(64000)
    assert not crypto_entry_price_ok(0.33)
    assert not crypto_entry_price_ok(0.09)
