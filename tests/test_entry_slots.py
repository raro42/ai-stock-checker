"""Entry slot interleave + breadth pulse honesty tests."""

import math

from stock_checker.entry_slots import interleave_asset_slots
from stock_checker.scan_breadth_gate import (
    pulse_from_opportunities,
    pulse_from_scan_lists,
)
from stock_checker.technical_indicators import coerce_score


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


def test_coerce_score_refuses_bool_allows_zero():
    assert coerce_score(0) == 0.0
    assert coerce_score(42.5) == 42.5
    assert coerce_score(True) is None
    assert coerce_score(False) is None
    assert coerce_score(math.nan) is None
    assert coerce_score(None) is None
    assert coerce_score("9") is None


def test_interleave_refuses_invalid_score_rank():
    """Bool/gap scores sort last — never invent True→1.0 ahead of real names."""
    opps = [
        {"symbol": "BTC-USD", "asset_class": "crypto", "score": True},
        {"symbol": "ETH-USD", "asset_class": "crypto", "score": 50},
        {"symbol": "AAPL", "asset_class": "stock", "score": math.nan},
        {"symbol": "MSFT", "asset_class": "stock", "score": 40},
    ]
    ordered = interleave_asset_slots(opps, max_crypto=2, max_stock=2)
    syms = [o["symbol"] for o in ordered]
    assert syms[0] == "ETH-USD"
    assert "MSFT" in syms
    # invalid crypto/stock still fill remaining slots after readable tops
    assert "BTC-USD" in syms
    assert "AAPL" in syms
    assert syms.index("ETH-USD") < syms.index("BTC-USD")
    assert syms.index("MSFT") < syms.index("AAPL")


def test_interleave_refuses_bool_slot_caps():
    """tradermonty #700/#655: True→1 / False→0 must not invent interleave caps."""
    from stock_checker.entry_pipeline import order_entry_candidates
    from stock_checker.entry_slots import (
        DEFAULT_MAX_CRYPTO_SLOTS,
        DEFAULT_MAX_STOCK_SLOTS,
    )

    opps = [
        {"symbol": "BTC-USD", "asset_class": "crypto", "score": 80},
        {"symbol": "ETH-USD", "asset_class": "crypto", "score": 70},
        {"symbol": "SOL-USD", "asset_class": "crypto", "score": 60},
        {"symbol": "AAPL", "asset_class": "stock", "score": 38},
        {"symbol": "MSFT", "asset_class": "stock", "score": 37},
        {"symbol": "GOOG", "asset_class": "stock", "score": 36},
        {"symbol": "AMZN", "asset_class": "stock", "score": 35},
    ]
    # Bool caps → defaults (2 crypto / 3 stock), not True→1 / False→0.
    ordered = interleave_asset_slots(
        opps,
        max_crypto=True,  # type: ignore[arg-type]
        max_stock=False,  # type: ignore[arg-type]
    )
    syms = [o["symbol"] for o in ordered]
    assert len([s for s in syms if s.endswith("-USD")]) == DEFAULT_MAX_CRYPTO_SLOTS
    assert len([s for s in syms if not s.endswith("-USD")]) == DEFAULT_MAX_STOCK_SLOTS
    via_pipeline = order_entry_candidates(
        opps,
        max_crypto=True,  # type: ignore[arg-type]
        max_stock=False,  # type: ignore[arg-type]
    )
    assert [o["symbol"] for o in via_pipeline] == syms


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
