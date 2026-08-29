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
    assert should_take_profit(8.0)
    assert not should_take_profit(7.9)
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

    # +3% was the old hurdle — still too thin vs −5% stops
    sell_mid, why_mid = should_rebalance_exit(
        profit_pct=3.0,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell_mid is False
    assert why_mid == "below rotate hurdle"

    sell2, why2 = should_rebalance_exit(
        profit_pct=5.0,
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell2 is True
    assert why2 == "rotate winner"

    held, why3 = should_rebalance_exit(
        profit_pct=8.0,
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


def test_pick_overweight_trim_prefers_winner_when_available():
    from stock_checker.exit_policy import pick_overweight_trim_candidate

    pick, why = pick_overweight_trim_candidate(
        [
            {"symbol": "WIN", "profit_pct": 3.0, "hold_seconds": 90000},
            {"symbol": "LOSE", "profit_pct": -2.0, "hold_seconds": 90000},
            {"symbol": "FRESH", "profit_pct": -9.0, "hold_seconds": 60},
        ],
        min_hold_seconds=14400,
    )
    assert pick == "WIN"
    assert "winner" in why


def test_pick_overweight_trim_prefers_worst_when_no_winner():
    from stock_checker.exit_policy import pick_overweight_trim_candidate

    pick, why = pick_overweight_trim_candidate(
        [
            {"symbol": "LOSE", "profit_pct": -2.0, "hold_seconds": 90000},
            {"symbol": "WORSE", "profit_pct": -4.0, "hold_seconds": 90000},
            {"symbol": "FRESH", "profit_pct": -9.0, "hold_seconds": 60},
        ],
        min_hold_seconds=14400,
    )
    assert pick == "WORSE"
    assert "worst mark" in why


def test_pick_overweight_trim_none_past_min_hold():
    from stock_checker.exit_policy import pick_overweight_trim_candidate

    none, why2 = pick_overweight_trim_candidate(
        [{"symbol": "FRESH", "profit_pct": -9.0, "hold_seconds": 60}],
        min_hold_seconds=14400,
    )
    assert none is None
    assert "min hold" in why2


def test_crypto_price_floor():
    assert crypto_entry_price_ok(1.0)
    assert crypto_entry_price_ok(64000)
    assert not crypto_entry_price_ok(0.33)
    assert not crypto_entry_price_ok(0.09)
