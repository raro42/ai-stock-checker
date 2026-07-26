#!/usr/bin/env python3
"""Tests for symbol long-name resolution."""

from pathlib import Path

from openbb_backend.symbol_names import (
    crypto_fallback_name,
    display_name,
    resolve_symbol_names,
)


def test_well_known_and_crypto(tmp_path: Path):
    names = resolve_symbol_names(
        ["BMY", "BTC-USD", "WMT"],
        tmp_path,
        live=False,
    )
    assert names["BMY"] == "Bristol-Myers Squibb"
    assert names["BTC-USD"] == "Bitcoin"
    assert names["WMT"] == "Walmart"
    assert display_name("BMY", names) == "Bristol-Myers Squibb"
    assert (tmp_path / "symbol_names.json").exists()


def test_live_fetcher_cached(tmp_path: Path):
    calls = []

    def fetch(sym: str):
        calls.append(sym)
        return "Fetched Co"

    names = resolve_symbol_names(
        ["ZZZ"],
        tmp_path,
        live=True,
        fetcher=fetch,
    )
    assert names["ZZZ"] == "Fetched Co"
    assert calls == ["ZZZ"]
    # Second pass hits cache — no more fetch
    names2 = resolve_symbol_names(["ZZZ"], tmp_path, live=True, fetcher=fetch)
    assert names2["ZZZ"] == "Fetched Co"
    assert calls == ["ZZZ"]


def test_crypto_fallback():
    assert crypto_fallback_name("ETH-USD") == "Ethereum"
    assert crypto_fallback_name("AAPL") is None
