"""Tests for paper exit / rotation policy."""

import math

from stock_checker.exit_policy import (
    book_action_mode,
    crypto_entry_price_ok,
    mark_price_ok,
    opportunity_symbol_set,
    should_allow_rebuy,
    should_rebalance_exit,
    should_stop_loss,
    should_take_profit,
    unrealized_profit_pct,
)


def test_take_profit_and_stop():
    assert should_take_profit(8.0)
    assert not should_take_profit(7.9)
    assert should_stop_loss(-5.0)
    assert not should_stop_loss(-4.9)


def test_take_profit_and_stop_refuse_bool():
    """tradermonty #700/#655: True→±1% must not invent TP/SL hits."""
    assert should_take_profit(True) is False  # type: ignore[arg-type]
    assert should_take_profit(1.5, threshold=True) is False  # type: ignore[arg-type]
    # Bool threshold falls back to default +8% — 1.5 stays below.
    assert should_take_profit(8.0, threshold=True) is True  # type: ignore[arg-type]
    assert should_stop_loss(True) is False  # type: ignore[arg-type]
    assert should_stop_loss(-0.5, threshold=True) is False  # type: ignore[arg-type]
    assert should_stop_loss(-5.0, threshold=True) is True  # type: ignore[arg-type]
    assert should_take_profit(math.nan) is False
    assert should_stop_loss(None) is False  # type: ignore[arg-type]


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


def test_rebuy_and_rotate_refuse_bool_knobs():
    """tradermonty #700/#655: True→1s / +1% must not invent clear/rotate."""
    blocked, why = should_allow_rebuy(
        seconds_since_exit=90000, cooldown_seconds=True  # type: ignore[arg-type]
    )
    assert blocked is False
    assert why == "rebuy cooldown"

    blocked2, why2 = should_allow_rebuy(
        seconds_since_exit=True, cooldown_seconds=86400  # type: ignore[arg-type]
    )
    assert blocked2 is False
    assert why2 == "rebuy cooldown"

    sell, why3 = should_rebalance_exit(
        profit_pct=True,  # type: ignore[arg-type]
        hold_seconds=86400,
        min_hold_seconds=14400,
    )
    assert sell is False
    assert why3 == "unreadable mark"

    sell2, why4 = should_rebalance_exit(
        profit_pct=8.0,
        hold_seconds=True,  # type: ignore[arg-type]
        min_hold_seconds=14400,
    )
    assert sell2 is False
    assert why4 == "min hold"

    sell3, why5 = should_rebalance_exit(
        profit_pct=8.0,
        hold_seconds=86400,
        min_hold_seconds=True,  # type: ignore[arg-type]
    )
    assert sell3 is False
    assert why5 == "min hold"

    # Bool rotate hurdle falls back to default 5% — +8% still rotates.
    sell4, why6 = should_rebalance_exit(
        profit_pct=8.0,
        hold_seconds=86400,
        min_hold_seconds=14400,
        rotate_min_profit_pct=True,  # type: ignore[arg-type]
    )
    assert sell4 is True
    assert why6 == "rotate winner"


def test_opportunity_symbol_set_includes_beyond_top_n():
    opps = [{"symbol": "A"}, {"symbol": "SCHW"}, {"symbol": "B"}]
    assert opportunity_symbol_set(opps) == {"A", "SCHW", "B"}
    assert opportunity_symbol_set([]) == set()


def test_book_action_mode():
    assert book_action_mode(3, 5) == "open"
    assert book_action_mode(5, 5) == "at_cap"
    assert book_action_mode(9, 5) == "overweight"


def test_book_action_mode_refuses_bool():
    """tradermonty #700/#655/#812: True must not invent at_cap 1/1 or overweight 5/1."""
    assert book_action_mode(True, 5) == "open"
    assert book_action_mode(5, True) == "open"
    assert book_action_mode(True, True) == "open"
    assert book_action_mode(False, 5) == "open"
    assert book_action_mode(5, False) == "open"
    assert book_action_mode(None, 5) == "open"  # type: ignore[arg-type]
    assert book_action_mode(5, None) == "open"  # type: ignore[arg-type]
    assert book_action_mode(math.nan, 5) == "open"  # type: ignore[arg-type]


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


def test_pick_overweight_trim_refuses_bool_hold_and_pct():
    """tradermonty #700/#655: True must not invent +1% winner or 1s past-hold."""
    import math

    from stock_checker.exit_policy import pick_overweight_trim_candidate

    pick, why = pick_overweight_trim_candidate(
        [
            {"symbol": "BOOL_PCT", "profit_pct": True, "hold_seconds": 90000},
            {"symbol": "BOOL_HOLD", "profit_pct": 3.0, "hold_seconds": True},
            {"symbol": "NAN", "profit_pct": math.nan, "hold_seconds": 90000},
            {"symbol": "WEAK", "profit_pct": 0.5, "hold_seconds": 90000},
            {"symbol": "LOSE", "profit_pct": -2.0, "hold_seconds": 90000},
        ],
        min_hold_seconds=14400,
    )
    assert pick == "WEAK"
    assert "winner" in why

    none, why2 = pick_overweight_trim_candidate(
        [
            {"symbol": "BOOL", "profit_pct": True, "hold_seconds": 90000},
            {"symbol": "FLAT", "profit_pct": False, "hold_seconds": 90000},
        ],
        min_hold_seconds=14400,
    )
    assert none is None
    assert "min hold" in why2

    none3, why3 = pick_overweight_trim_candidate(
        [{"symbol": "WEAK", "profit_pct": 0.5, "hold_seconds": 90000}],
        min_hold_seconds=True,  # type: ignore[arg-type]
    )
    assert none3 is None
    assert "unreadable min hold" in why3


def test_crypto_price_floor():
    assert crypto_entry_price_ok(1.0)
    assert crypto_entry_price_ok(64000)
    assert not crypto_entry_price_ok(0.33)
    assert not crypto_entry_price_ok(0.09)
    # tradermonty #655/#754: bool/NaN/None must not look like a $1+ mark
    assert not crypto_entry_price_ok(True)
    assert not crypto_entry_price_ok(math.nan)
    assert not crypto_entry_price_ok(None)
    # Bool floor falls back to default $1 — 0.5 still blocked; 1.0 ok.
    assert not crypto_entry_price_ok(0.5, min_usd=True)  # type: ignore[arg-type]
    assert crypto_entry_price_ok(1.0, min_usd=True)  # type: ignore[arg-type]


def test_mark_price_ok_refuses_invalid():
    assert mark_price_ok(100.0)
    assert not mark_price_ok(True)
    assert not mark_price_ok(0)
    assert not mark_price_ok(-1)
    assert not mark_price_ok(math.nan)
    assert not mark_price_ok(None)
    assert not mark_price_ok("12.5")


def test_unrealized_profit_pct_refuses_invalid_mark():
    assert unrealized_profit_pct(110.0, 100.0) == 10.0
    assert unrealized_profit_pct(True, 100.0) is None
    assert unrealized_profit_pct(110.0, True) is None
    assert unrealized_profit_pct(0, 100.0) is None
    assert unrealized_profit_pct(math.nan, 100.0) is None
    assert unrealized_profit_pct(110.0, 0) is None
