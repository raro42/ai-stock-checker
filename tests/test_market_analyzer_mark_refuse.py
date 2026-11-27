"""MarketAnalyzer close/% must refuse bool invents (tradermonty #700/#655)."""

from __future__ import annotations

from stock_checker.market_analyzer import MarketAnalyzer
from stock_checker.recommender import RecommendationEngine


def test_get_top_movers_skips_bool_closes(monkeypatch) -> None:
    """True→$1 closes must not invent a mover row."""
    analyzer = MarketAnalyzer()
    monkeypatch.setattr(analyzer, "get_sp500_components", lambda: ["BAD", "OK"])

    class _Series:
        def __init__(self, vals):
            self._vals = vals

        @property
        def iloc(self):
            return self

        def __getitem__(self, idx: int):
            return self._vals[idx]

    class _Hist:
        def __init__(self, closes):
            self.empty = False
            self._closes = closes

        def __len__(self) -> int:
            return len(self._closes)

        def __getitem__(self, key: str):
            assert key == "Close"
            return _Series(self._closes)

    def _fake_hist(symbol, period="1d", **_k):
        if symbol == "BAD":
            return _Hist([True, True])
        return _Hist([100.0, 110.0])

    class _Ticker:
        def __init__(self, symbol: str):
            self.symbol = symbol
            self.info = {"longName": symbol, "volume": 100, "marketCap": 1e9}

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history", _fake_hist
    )
    monkeypatch.setattr("stock_checker.market_analyzer.yf.Ticker", _Ticker)
    out = analyzer.get_top_movers(limit=10)
    assert [row["symbol"] for row in out] == ["OK"]
    assert out[0]["change_pct"] == 10.0
    assert out[0]["volume"] == 100.0


def test_get_top_movers_skips_history_timeout(monkeypatch) -> None:
    """Hung Yahoo join timeout must skip the name (not stall the movers strip)."""
    analyzer = MarketAnalyzer()
    monkeypatch.setattr(analyzer, "get_sp500_components", lambda: ["HANG", "OK"])

    class _Series:
        def __init__(self, vals):
            self._vals = vals

        @property
        def iloc(self):
            return self

        def __getitem__(self, idx: int):
            return self._vals[idx]

    class _Hist:
        empty = False

        def __len__(self) -> int:
            return 2

        def __getitem__(self, key: str):
            return _Series([100.0, 110.0])

    def _fake_hist(symbol, period="1d", **_k):
        if symbol == "HANG":
            raise TimeoutError("yfinance history HANG timed out after 20s")
        return _Hist()

    class _Ticker:
        def __init__(self, symbol: str):
            self.info = {"longName": symbol, "volume": 50, "marketCap": 1e9}

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history", _fake_hist
    )
    monkeypatch.setattr("stock_checker.market_analyzer.yf.Ticker", _Ticker)
    out = analyzer.get_top_movers(limit=10)
    assert [row["symbol"] for row in out] == ["OK"]


def test_get_period_change_unavailable_not_flat_zero(monkeypatch) -> None:
    """Missing/bool bars → None (never invent flat 0.0% change)."""
    analyzer = MarketAnalyzer()

    class _Empty:
        empty = True

        def __len__(self) -> int:
            return 0

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history",
        lambda *_a, **_k: _Empty(),
    )
    assert analyzer._get_period_change("AAPL", "1d") is None

    class _Series:
        def __init__(self, vals):
            self._vals = vals

        @property
        def iloc(self):
            return self

        def __getitem__(self, idx: int):
            return self._vals[idx]

    class _BoolHist:
        empty = False

        def __len__(self) -> int:
            return 2

        def __getitem__(self, key: str):
            return _Series([True, False])

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history",
        lambda *_a, **_k: _BoolHist(),
    )
    assert analyzer._get_period_change("AAPL", "1d") is None


def test_get_period_change_timeout_unavailable(monkeypatch) -> None:
    """History timeout → None (never invent flat 0.0%)."""
    analyzer = MarketAnalyzer()

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 20s")

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history", _boom
    )
    assert analyzer._get_period_change("AAPL", "1d") is None


def test_bitcoin_recommender_reads_change_1d_alias() -> None:
    """MarketAnalyzer change_1d must score (not silent flat-0 via missing daily_change)."""
    eng = RecommendationEngine()
    aliased = eng.analyze_bitcoin_recommendation({"change_1d": 6.0})
    legacy = eng.analyze_bitcoin_recommendation({"daily_change": 6.0})
    quiet = eng.analyze_bitcoin_recommendation({})
    assert aliased["score"] == legacy["score"]
    assert aliased["score"] is not None and aliased["score"] > 0
    assert quiet["score"] is None
    assert quiet["action"] == "unavailable"


def test_bitcoin_recommender_refuses_bool_change_1d() -> None:
    """True→1.0% must not invent mild BTC momentum via change_1d alias."""
    eng = RecommendationEngine()
    bad = eng.analyze_bitcoin_recommendation({"change_1d": True})
    quiet = eng.analyze_bitcoin_recommendation({})
    assert bad["score"] is None
    assert bad["action"] == "unavailable"
    assert bad["score"] == quiet["score"]
