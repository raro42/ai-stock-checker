"""Legacy PaperTrader knobs must refuse bool invents."""

from __future__ import annotations

from stock_checker.paper_trader import (
    DEFAULT_CHECK_INTERVAL_SEC,
    DEFAULT_POSITION_SIZE_PCT,
    PaperTrader,
    _coerce_paper_frac,
    _coerce_paper_interval,
    _coerce_paper_iteration,
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
