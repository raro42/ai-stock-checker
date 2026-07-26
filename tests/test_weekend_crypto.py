"""Weekend trading policy tests."""

from stock_checker.market_scanner import MarketScanner


def test_weekend_detection_helpers_exist():
    scanner = MarketScanner(top_crypto_count=2)
    assert hasattr(scanner, "is_weekend")
    assert hasattr(scanner, "is_market_closed")
    assert isinstance(scanner.is_weekend(), bool)
