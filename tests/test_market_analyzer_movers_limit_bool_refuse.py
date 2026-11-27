"""MarketAnalyzer movers strip limit must refuse bool invents."""

from __future__ import annotations

from stock_checker.market_analyzer import (
    DEFAULT_TOP_MOVERS_LIMIT,
    MarketAnalyzer,
    _coerce_movers_limit,
)


def test_coerce_movers_limit_refuses_bool() -> None:
    """True→1 / [:True] must not invent a one-name CLI/monitor movers strip."""
    assert _coerce_movers_limit(True) == DEFAULT_TOP_MOVERS_LIMIT
    assert _coerce_movers_limit(False) == DEFAULT_TOP_MOVERS_LIMIT
    assert _coerce_movers_limit(0) == DEFAULT_TOP_MOVERS_LIMIT
    assert _coerce_movers_limit(None) == DEFAULT_TOP_MOVERS_LIMIT
    assert _coerce_movers_limit(48) == 48
    assert _coerce_movers_limit(5) == 5


def test_get_top_movers_bool_limit_falls_back_to_default(monkeypatch) -> None:
    """Damaged limit=True must not slice movers to a one-row strip."""
    analyzer = MarketAnalyzer()
    symbols = [f"S{i}" for i in range(15)]
    monkeypatch.setattr(analyzer, "get_sp500_components", lambda: symbols)

    class _Hist:
        empty = False

        def __len__(self) -> int:
            return 2

        def __getitem__(self, key: str):
            class _Close:
                def iloc(self):  # pragma: no cover - attribute style
                    raise AssertionError

            class _Series:
                def __init__(self, vals):
                    self._vals = vals

                @property
                def iloc(self):
                    return self

                def __getitem__(self, idx: int):
                    return self._vals[idx]

            return _Series([100.0, 100.0 + float(getattr(self, "_i", 1))])

    calls = {"i": 0}

    def _fake_hist(symbol, period="1d", **_k):
        calls["i"] += 1
        h = _Hist()
        h._i = calls["i"]  # type: ignore[attr-defined]
        return h

    def _fake_info(symbol, **_k):
        return {"longName": symbol, "volume": 1, "marketCap": 1}

    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_history",
        _fake_hist,
    )
    monkeypatch.setattr(
        "stock_checker.market_analyzer.fetch_yfinance_info",
        _fake_info,
    )
    out = analyzer.get_top_movers(limit=True)
    assert len(out) == DEFAULT_TOP_MOVERS_LIMIT
