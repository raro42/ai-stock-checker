"""Offline tests for Screener scalar opportunity counts (display only)."""

from openbb_backend.desk import build_screener_opportunity_counts


def test_empty_and_non_mapping():
    empty = build_screener_opportunity_counts(None)
    assert empty["n_total"] == 0
    assert empty["n_unique"] == 0
    assert empty["lists_populated"] == 0
    assert empty["weight"] == "row slots"
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
    assert c["lists_populated"] == 2
    assert c["overlap"] is False
    assert c["weight"] == "row slots"


def test_overlap_speaks_unique():
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "NVDA"}, {"symbol": "AAPL"}],
            "crypto_leaders": [{"symbol": "BTC-USD"}],
            "stock_breakouts": [{"symbol": "NVDA"}],
        }
    )
    assert c["n_total"] == 4
    assert c["n_unique"] == 3
    assert c["overlap"] is True
    assert c["weight"] == "3 unique"
    assert c["lists_populated"] == 3


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
    assert c["weight"] == "2 unique"
