"""Offline tests for scan-list breadth gate."""

import math

from stock_checker.scan_breadth_gate import (
    new_entry_breadth_allowed,
    pulse_from_opportunities,
    summarize_pulse,
)


def test_pulse_from_opportunities():
    pulse = pulse_from_opportunities(
        [
            {"symbol": "BTC-USD", "change_24h": 2.0},
            {"symbol": "ETH-USD", "change_24h": -1.0},
            {"symbol": "AAPL", "pct_from_high": 2.0, "score": 10},
            {"symbol": "MSFT", "pct_from_high": 40.0, "score": -5},
        ]
    )
    assert pulse["crypto_up"] == 1
    assert pulse["crypto_down"] == 1
    assert pulse["stock_leaders"] == 1
    assert pulse["stock_n"] == 2


def test_pulse_refuses_bool_nan_no_invent_breadth():
    """tradermonty #798/#655 + xang1234: True→1.0 must not invent up / leader."""
    pulse = pulse_from_opportunities(
        [
            {"symbol": "BTC-USD", "change_24h": True},
            {"symbol": "ETH-USD", "change_24h": math.nan},
            {"symbol": "SOL-USD", "change_24h": False},
            {"symbol": "AAPL", "pct_from_high": True, "score": True},
            {"symbol": "MSFT", "pct_from_high": math.nan},
            {"symbol": "NVDA", "pct_from_high": 1.0},  # real near-high
        ]
    )
    assert pulse["crypto_up"] == 0
    assert pulse["crypto_down"] == 0
    assert pulse["crypto_n"] == 0
    assert pulse["crypto_missing_chg"] == 3
    assert pulse["stock_n"] == 3
    assert pulse["stock_leaders"] == 1


def test_crypto_breadth_blocks_when_weak():
    pulse = {"crypto_up": 1, "crypto_down": 4, "stock_n": 0, "stock_leaders": 0}
    ok, why = new_entry_breadth_allowed(
        is_crypto=True, pulse=pulse, enabled=True, min_ratio=0.4
    )
    assert not ok
    assert "weak" in why


def test_crypto_breadth_allows_when_strong():
    pulse = {"crypto_up": 3, "crypto_down": 1, "stock_n": 0, "stock_leaders": 0}
    ok, _ = new_entry_breadth_allowed(
        is_crypto=True, pulse=pulse, enabled=True, min_ratio=0.4
    )
    assert ok


def test_stock_breadth_and_fail_open():
    blocked, _ = new_entry_breadth_allowed(
        is_crypto=False,
        pulse={"crypto_up": 0, "crypto_down": 0, "stock_n": 5, "stock_leaders": 0},
        enabled=True,
        min_leaders=1,
    )
    assert not blocked

    ok, why = new_entry_breadth_allowed(
        is_crypto=False, pulse=None, enabled=True
    )
    assert ok
    assert "unknown" in why

    ok_off, _ = new_entry_breadth_allowed(
        is_crypto=True,
        pulse={"crypto_up": 0, "crypto_down": 9},
        enabled=False,
    )
    assert ok_off


def test_breadth_gate_refuses_bool_pulse_counts():
    """tradermonty #700/#655: int(True) must not invent advance / leaders."""
    # Damaged bool A/D → unknown (fail-open), not a fake 1-up sample.
    ok, why = new_entry_breadth_allowed(
        is_crypto=True,
        pulse={"crypto_up": True, "crypto_down": False},
        enabled=True,
        min_ratio=0.4,
    )
    assert ok
    assert "unknown" in why

    # Bool stock_n alone must not invent a 1-name book that looks thin.
    ok2, why2 = new_entry_breadth_allowed(
        is_crypto=False,
        pulse={"stock_n": True, "stock_leaders": False},
        enabled=True,
        min_leaders=1,
    )
    assert ok2
    assert "unknown" in why2

    # False→0 would clear the leader floor; refuse → default 1 → still thin.
    ok3, why3 = new_entry_breadth_allowed(
        is_crypto=False,
        pulse={"stock_n": 5, "stock_leaders": 0},
        enabled=True,
        min_leaders=False,
    )
    assert not ok3
    assert "thin" in why3

    # True→1.0 would demand ≥95% and block a mild 50% advance; refuse → 40% allow.
    ok4, why4 = new_entry_breadth_allowed(
        is_crypto=True,
        pulse={"crypto_up": 1, "crypto_down": 1},
        enabled=True,
        min_ratio=True,
    )
    assert ok4
    assert "ok" in why4

    assert summarize_pulse(
        {
            "crypto_up": True,
            "crypto_down": False,
            "stock_leaders": True,
            "stock_n": False,
        }
    ) == "crypto 0↑/0↓ · stock leaders 0/0"
