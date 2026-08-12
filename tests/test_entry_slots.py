"""Entry slot interleave + breadth pulse honesty tests."""

from stock_checker.entry_slots import interleave_asset_slots
from stock_checker.scan_breadth_gate import (
    pulse_from_opportunities,
    pulse_from_scan_lists,
)


def test_interleave_prefers_both_asset_classes():
    opps = [
        {"symbol": "BTC-USD", "asset_class": "crypto", "score": 80},
        {"symbol": "ETH-USD", "asset_class": "crypto", "score": 70},
        {"symbol": "SOL-USD", "asset_class": "crypto", "score": 60},
        {"symbol": "AAPL", "asset_class": "stock", "score": 38},
        {"symbol": "MSFT", "asset_class": "stock", "score": 37},
    ]
    ordered = interleave_asset_slots(opps, max_crypto=2, max_stock=2)
    syms = [o["symbol"] for o in ordered]
    assert "BTC-USD" in syms and "AAPL" in syms
    assert "SOL-USD" not in syms  # crypto capped at 2
    assert syms.index("AAPL") < len(syms)


def test_pulse_from_enriched_recommendations():
    """Recommendations without raw fields used to starve stock leaders — fixed."""
    pulse = pulse_from_opportunities(
        [
            {"symbol": "BTC-USD", "change_24h": 1.5},
            {"symbol": "AAPL", "pct_from_high": -2.0, "score": 38.0},
        ]
    )
    assert pulse["crypto_up"] == 1
    assert pulse["stock_n"] == 1
    assert pulse["stock_leaders"] == 1


def test_pulse_from_scan_lists_prefers_leaders():
    pulse = pulse_from_scan_lists(
        crypto_leaders=[{"symbol": "BTC-USD", "change_24h": -2.0}],
        stock_breakouts=[{"symbol": "AAPL", "pct_from_high": -1.0}],
        recommendations=[],
    )
    assert pulse["crypto_down"] == 1
    assert pulse["stock_leaders"] == 1
