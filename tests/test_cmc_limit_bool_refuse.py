"""CoinMarketCapFetcher strip limits must refuse bool invents."""

from __future__ import annotations

from stock_checker.coinmarketcap_fetcher import (
    DEFAULT_TOP_MOVERS_LISTING_LIMIT,
    DEFAULT_TRENDING_LIMIT,
    _coerce_cmc_limit,
)


def test_coerce_cmc_limit_refuses_bool() -> None:
    """True→1 / [:True] must not invent a one-coin trending strip."""
    assert _coerce_cmc_limit(True, DEFAULT_TRENDING_LIMIT) == DEFAULT_TRENDING_LIMIT
    assert _coerce_cmc_limit(False, DEFAULT_TRENDING_LIMIT) == DEFAULT_TRENDING_LIMIT
    assert _coerce_cmc_limit(0, DEFAULT_TRENDING_LIMIT) == DEFAULT_TRENDING_LIMIT
    assert _coerce_cmc_limit(None, DEFAULT_TRENDING_LIMIT) == DEFAULT_TRENDING_LIMIT
    assert _coerce_cmc_limit(48, DEFAULT_TRENDING_LIMIT) == 48


def test_coerce_cmc_listing_limit_refuses_bool() -> None:
    """True→1 must not invent a one-row listing fetch for top movers."""
    assert (
        _coerce_cmc_limit(True, DEFAULT_TOP_MOVERS_LISTING_LIMIT)
        == DEFAULT_TOP_MOVERS_LISTING_LIMIT
    )
    assert (
        _coerce_cmc_limit(False, DEFAULT_TOP_MOVERS_LISTING_LIMIT)
        == DEFAULT_TOP_MOVERS_LISTING_LIMIT
    )
    assert _coerce_cmc_limit(50, DEFAULT_TOP_MOVERS_LISTING_LIMIT) == 50
