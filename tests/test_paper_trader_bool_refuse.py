"""Legacy PaperTrader knobs must refuse bool invents."""

from __future__ import annotations

from stock_checker.paper_trader import (
    DEFAULT_AUTO_PROFIT_TARGET_PCT,
    DEFAULT_AUTO_STOP_LOSS_PCT,
    DEFAULT_CHECK_INTERVAL_SEC,
    DEFAULT_POSITION_SIZE_PCT,
    PaperTrader,
    _coerce_paper_frac,
    _coerce_paper_interval,
    _coerce_paper_iteration,
    _paper_auto_exit_bands,
    _paper_vol_adjustment_pct,
)


def test_coerce_paper_interval_refuses_bool() -> None:
    assert _coerce_paper_interval(True) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_paper_interval(False) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_paper_interval(0) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_paper_interval(None) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_paper_interval(120) == 120


def test_coerce_paper_frac_refuses_bool() -> None:
    assert _coerce_paper_frac(True, DEFAULT_POSITION_SIZE_PCT) == DEFAULT_POSITION_SIZE_PCT
    assert _coerce_paper_frac(False, DEFAULT_POSITION_SIZE_PCT) == DEFAULT_POSITION_SIZE_PCT
    assert _coerce_paper_frac(1.5, DEFAULT_POSITION_SIZE_PCT) == DEFAULT_POSITION_SIZE_PCT
    assert _coerce_paper_frac(0.2, DEFAULT_POSITION_SIZE_PCT) == 0.2


def test_coerce_paper_iteration_refuses_bool() -> None:
    assert _coerce_paper_iteration(True) == 0
    assert _coerce_paper_iteration(False) == 0
    assert _coerce_paper_iteration(None) == 0
    assert _coerce_paper_iteration(7) == 7


def test_paper_trader_ctor_refuses_bool_knobs(tmp_path) -> None:
    t = PaperTrader(
        check_interval=True,
        position_size_pct=True,
        data_dir=str(tmp_path),
        ai_mode="off",
    )
    assert t.check_interval == DEFAULT_CHECK_INTERVAL_SEC
    assert t.position_size_pct == DEFAULT_POSITION_SIZE_PCT
    assert t.base_position_size == DEFAULT_POSITION_SIZE_PCT

    t2 = PaperTrader(
        check_interval=90,
        position_size_pct=0.12,
        data_dir=str(tmp_path / "ok"),
        ai_mode="off",
    )
    assert t2.check_interval == 90
    assert t2.position_size_pct == 0.12


def test_dynamic_size_refuses_bool_volatility(tmp_path) -> None:
    t = PaperTrader(data_dir=str(tmp_path), ai_mode="off")
    rec = {"confidence": "MEDIUM"}
    # True→1.0 vol must not shrink size as if 100% daily vol
    sized = t.calculate_dynamic_position_size("AAPL", rec, {"volatility_30d": True})
    assert sized == t.base_position_size
    # Real high vol still shrinks
    hot = t.calculate_dynamic_position_size("AAPL", rec, {"volatility_30d": 0.10})
    assert hot < t.base_position_size


def test_paper_vol_adjustment_refuses_bool() -> None:
    # True→1.0 would invent +150pp (1.0×100×1.5) on auto TP/SL
    assert _paper_vol_adjustment_pct(True) == 0.0
    assert _paper_vol_adjustment_pct(False) == 0.0
    assert _paper_vol_adjustment_pct(None) == 0.0
    assert _paper_vol_adjustment_pct("0.05") == 0.0
    assert _paper_vol_adjustment_pct(0.05) == 7.5


def test_paper_auto_exit_bands_refuse_bool_vol() -> None:
    tp, sl = _paper_auto_exit_bands(True)
    assert tp == DEFAULT_AUTO_PROFIT_TARGET_PCT
    assert sl == DEFAULT_AUTO_STOP_LOSS_PCT
    tp2, sl2 = _paper_auto_exit_bands(0.05)
    assert tp2 == DEFAULT_AUTO_PROFIT_TARGET_PCT + 7.5
    assert sl2 == DEFAULT_AUTO_STOP_LOSS_PCT + 7.5
    tp3, sl3 = _paper_auto_exit_bands(None)
    assert tp3 == DEFAULT_AUTO_PROFIT_TARGET_PCT
    assert sl3 == DEFAULT_AUTO_STOP_LOSS_PCT


def test_execute_trade_refuses_bool_mark(tmp_path) -> None:
    """True→€1 must not invent sizing / score before Portfolio fill refuse."""
    t = PaperTrader(data_dir=str(tmp_path), ai_mode="off")
    before = dict(t.portfolio.holdings)
    rec = {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": "HIGH",
        "score": True,
        "reasons": ["test"],
    }
    t.execute_trade(rec, True, {})
    assert t.portfolio.holdings == before
    # Usable mark still sizes (may or may not fill depending on cash/score path)
    t.execute_trade({**rec, "score": 12}, 150.0, {})
    # No crash; score coerce path exercised


def test_detect_market_regime_refuses_unreadable_marks(tmp_path) -> None:
    """Missing/bool SPX% or VIX must not invent calm flat 0% / VIX=20 sideways."""
    t = PaperTrader(data_dir=str(tmp_path), ai_mode="off")

    def _spx_gap(_sym: str) -> dict:
        return {"daily_change": None} if _sym == "^GSPC" else {"current_price": 15.0}

    t.fetcher.get_stock_info = _spx_gap  # type: ignore[method-assign]
    assert t._detect_market_regime() == "neutral"

    def _spx_bool(_sym: str) -> dict:
        return {"daily_change": True} if _sym == "^GSPC" else {"current_price": 15.0}

    t.fetcher.get_stock_info = _spx_bool  # type: ignore[method-assign]
    assert t._detect_market_regime() == "neutral"

    def _vix_gap(_sym: str) -> dict:
        return {"daily_change": 2.0} if _sym == "^GSPC" else {"current_price": None}

    t.fetcher.get_stock_info = _vix_gap  # type: ignore[method-assign]
    assert t._detect_market_regime() == "neutral"

    def _vix_bool(_sym: str) -> dict:
        return {"daily_change": 2.0} if _sym == "^GSPC" else {"current_price": True}

    t.fetcher.get_stock_info = _vix_bool  # type: ignore[method-assign]
    assert t._detect_market_regime() == "neutral"

    def _ok_bull(_sym: str) -> dict:
        return {"daily_change": 2.0} if _sym == "^GSPC" else {"current_price": 15.0}

    t.fetcher.get_stock_info = _ok_bull  # type: ignore[method-assign]
    assert t._detect_market_regime() == "bull"

    def _ok_sideways(_sym: str) -> dict:
        return {"daily_change": 0.2} if _sym == "^GSPC" else {"current_price": 18.0}

    t.fetcher.get_stock_info = _ok_sideways  # type: ignore[method-assign]
    assert t._detect_market_regime() == "sideways"
