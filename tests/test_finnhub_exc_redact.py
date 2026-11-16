"""tradermonty #778: Finnhub RequestException paths never echo token= URLs."""

from __future__ import annotations

import pytest
import requests

from stock_checker.fetcher import StockFetcher
from stock_checker.finnhub_fetcher import FinnhubFetcher


def test_finnhub_request_exception_is_class_only(monkeypatch):
    secret = "finnhubRaiseLeak99"  # pragma: allowlist secret
    monkeypatch.setenv("FINNHUB_API_KEY", secret)
    fetcher = FinnhubFetcher(api_key=secret)
    monkeypatch.setattr(fetcher, "_wait_for_rate_limit", lambda: None)

    def boom(*_a, **_k):
        raise requests.exceptions.Timeout(
            f"https://finnhub.io/api/v1/quote?symbol=MSFT&token={secret}"
        )

    monkeypatch.setattr(fetcher.session, "get", boom)

    with pytest.raises(ValueError) as caught:
        fetcher.get_stock_info("MSFT")

    msg = str(caught.value)
    assert secret not in msg
    assert "token=" not in msg
    assert "Timeout" in msg
    assert "MSFT" in msg


def test_historical_data_exception_is_redacted(monkeypatch):
    """StockFetcher history raises must not echo token= query strings."""
    secret = "histExcLeak99"  # pragma: allowlist secret

    class BoomTicker:
        def history(self, *_a, **_k):
            raise ConnectionError(
                f"Max retries with url: /v1/quote?symbol=AAPL&token={secret}"
            )

    monkeypatch.setattr(
        "stock_checker.fetcher.yf.Ticker", lambda *_a, **_k: BoomTicker()
    )

    with pytest.raises(ValueError) as caught:
        StockFetcher().get_historical_data("AAPL", period="1mo")

    msg = str(caught.value)
    assert secret not in msg
    assert "token=REDACTED" in msg
    assert "AAPL" in msg


def test_binance_console_exception_is_redacted(monkeypatch, capsys):
    """tradermonty #778 follow-up: Binance console must not echo token= URLs."""
    secret = "binanceExcLeak99"  # pragma: allowlist secret
    from stock_checker.binance_fetcher import BinanceFetcher

    fetcher = BinanceFetcher()

    def boom(*_a, **_k):
        raise requests.exceptions.ConnectionError(
            f"Max retries with url: /api/v3/ticker/24hr?symbol=BTCUSDT&token={secret}"
        )

    monkeypatch.setattr(fetcher.session, "get", boom)
    assert fetcher.get_crypto_price("BTCUSDT") is None
    err = capsys.readouterr().out
    assert secret not in err
    assert "token=REDACTED" in err


def test_cmc_console_exception_is_redacted(monkeypatch, capsys):
    """tradermonty #778 follow-up: CMC console must not echo apikey= URLs."""
    secret = "cmcExcLeakKey99"  # pragma: allowlist secret
    from stock_checker.coinmarketcap_fetcher import CoinMarketCapFetcher

    fetcher = CoinMarketCapFetcher()

    def boom(*_a, **_k):
        raise requests.exceptions.ConnectionError(
            f"HTTPSConnectionPool: url: /data-api/v3/spotlight?apikey={secret}"
        )

    monkeypatch.setattr(fetcher.session, "get", boom)
    out = fetcher.get_trending_gainers_losers()
    assert out["gainers"] == []
    err = capsys.readouterr().out
    assert secret not in err
    assert "apikey=REDACTED" in err


def test_intelligent_trader_console_has_no_raw_str_e():
    """tradermonty #778: buy/sell/AI/trade console paths must use safe_exc_text."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "stock_checker"
        / "intelligent_trader.py"
    ).read_text(encoding="utf-8")
    assert "str(e)" not in src
    assert "safe_exc_text" in src
    assert "redact_secrets(traceback.format_exc())" in src


def test_scanner_universe_ai_console_has_no_raw_exc_echo():
    """tradermonty #778 follow-up: scanner/universe/AI recommender console redact."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "stock_checker"
    for name in (
        "market_scanner.py",
        "stock_universe_manager.py",
        "ai_recommender.py",
    ):
        src = (root / name).read_text(encoding="utf-8")
        assert "str(e)" not in src, name
        assert "{e}" not in src, name
        assert "safe_exc_text" in src, name


def test_cli_ai_market_analyzer_has_no_raw_exc_echo():
    """tradermonty #778 follow-up: friend CLI + analyzer return strings redact."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "stock_checker"
    for name in ("cli.py", "ai_analyzer.py", "market_analyzer.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "str(e)" not in src, name
        assert "safe_exc_text" in src, name


def test_ai_analyzer_urlerror_is_redacted(monkeypatch):
    """Ollama URLError returns must not echo token= query strings."""
    import urllib.error
    import urllib.request

    from stock_checker.ai_analyzer import OllamaAnalyzer

    secret = "ollamaExcLeak99"  # pragma: allowlist secret

    def boom(*_a, **_k):
        raise urllib.error.URLError(
            f"https://localhost/api/generate?token={secret}"
        )

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = OllamaAnalyzer().analyze_stock({"symbol": "AAPL", "name": "Apple"})
    assert secret not in out
    assert "token=REDACTED" in out


def test_market_analyzer_bitcoin_exc_is_redacted(monkeypatch):
    """Bitcoin fetch ValueError must not echo token= query strings."""
    secret = "btcExcLeak99"  # pragma: allowlist secret
    from stock_checker.market_analyzer import MarketAnalyzer

    class BoomTicker:
        @property
        def info(self):
            raise ConnectionError(
                f"Max retries with url: /v8/finance/chart/BTC-USD?token={secret}"
            )

        def history(self, *_a, **_k):
            raise ConnectionError(
                f"Max retries with url: /v8/finance/chart/BTC-USD?token={secret}"
            )

    monkeypatch.setattr(
        "stock_checker.market_analyzer.yf.Ticker",
        lambda *_a, **_k: BoomTicker(),
    )
    with pytest.raises(ValueError) as caught:
        MarketAnalyzer().get_bitcoin_data()
    msg = str(caught.value)
    assert secret not in msg
    assert "token=REDACTED" in msg
