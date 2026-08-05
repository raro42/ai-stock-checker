"""Offline tests for scan-list breadth gate."""

from stock_checker.scan_breadth_gate import (
    new_entry_breadth_allowed,
    pulse_from_opportunities,
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
