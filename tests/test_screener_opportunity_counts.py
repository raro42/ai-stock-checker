"""Offline tests for Screener scalar opportunity counts (display only)."""

from openbb_backend.desk import build_screener_opportunity_counts


def test_empty_and_non_mapping():
    empty = build_screener_opportunity_counts(None)
    assert empty["n_total"] == 0
    assert empty["n_unique"] == 0
    assert empty["n_dup"] == 0
    assert empty["lists_populated"] == 0
    assert empty["weight"] == "row slots"
    assert empty["unique_share_pct"] is None
    assert empty["tone"] == "flat"
    assert build_screener_opportunity_counts("bad")["n_total"] == 0


def test_scalar_list_lengths():
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, {"symbol": "MSFT"}],
            "crypto_leaders": [{"symbol": "BTC-USD"}],
            "stock_breakouts": [],
        }
    )
    assert c["n_rec"] == 2
    assert c["n_crypto"] == 1
    assert c["n_brk"] == 0
    assert c["n_total"] == 3
    assert c["n_unique"] == 3
    assert c["n_dup"] == 0
    assert c["lists_populated"] == 2
    assert c["overlap"] is False
    assert c["unique_share_pct"] is None
    assert c["weight"] == "row slots"
    assert c["tone"] == "flat"


def test_overlap_speaks_unique_share_ok():
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "NVDA"}, {"symbol": "AAPL"}],
            "crypto_leaders": [{"symbol": "BTC-USD"}],
            "stock_breakouts": [{"symbol": "NVDA"}],
        }
    )
    assert c["n_total"] == 4
    assert c["n_unique"] == 3
    assert c["n_dup"] == 1
    assert c["overlap"] is True
    assert c["unique_share_pct"] == 75.0
    assert c["unique_share_severity"] == "strong"
    assert c["weight"] == "3 unique · strong · 75%"
    assert c["tone"] == "flat"
    assert c["lists_populated"] == 3


def test_overlap_unique_share_thin_warns():
    # 2 unique across 5 slots → 40% thin
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, {"symbol": "AAPL"}],
            "crypto_leaders": [{"symbol": "AAPL"}],
            "stock_breakouts": [{"symbol": "MSFT"}, {"symbol": "AAPL"}],
        }
    )
    assert c["n_total"] == 5
    assert c["n_unique"] == 2
    assert c["n_dup"] == 3
    assert c["unique_share_pct"] == 40.0
    assert c["unique_share_severity"] == "thin"
    assert c["weight"] == "2 unique · thin · 40%"
    assert c["tone"] == "warn"


def test_overlap_unique_share_mid_ok():
    # 3 unique / 5 slots → 60% mid (ok, no lean word)
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}],
            "crypto_leaders": [{"symbol": "A"}],
            "stock_breakouts": [{"symbol": "B"}],
        }
    )
    assert c["n_total"] == 5
    assert c["n_unique"] == 3
    assert c["unique_share_pct"] == 60.0
    assert c["unique_share_severity"] == "ok"
    assert c["weight"] == "3 unique · 60%"
    assert c["tone"] == "flat"


def test_string_symbols_and_bad_list_type():
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["aapl", "msft"],
            "crypto_leaders": "not-a-list",
            "stock_breakouts": [{"symbol": "AAPL"}],
        }
    )
    assert c["n_rec"] == 2
    assert c["n_crypto"] == 0
    assert c["n_brk"] == 1
    assert c["n_total"] == 3
    assert c["n_unique"] == 2
    assert c["overlap"] is True
    assert c["unique_share_pct"] == 66.7
    assert c["unique_share_severity"] == "ok"
    assert c["weight"] == "2 unique · 66.7%"
