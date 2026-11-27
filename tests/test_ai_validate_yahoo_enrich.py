"""tradermonty #896/#655: AI-validate Yahoo enrich must not invent tape."""

from __future__ import annotations

from stock_checker.intelligent_trader import _ai_validate_apply_yahoo_info


def test_ai_validate_apply_yahoo_info_refuses_bool_and_fills_readable() -> None:
    row = {
        "volume": None,
        "pe_ratio": None,
        "52_week_high": None,
        "52_week_low": None,
        "previous_close": None,
    }
    _ai_validate_apply_yahoo_info(
        row,
        {
            "volume": True,
            "regularMarketVolume": 12_500_000.0,
            "trailingPE": False,
            "forwardPE": 18.5,
            "fiftyTwoWeekHigh": True,
            "fiftyTwoWeekLow": 90.0,
            "previousClose": 100.0,
        },
    )
    assert row["volume"] == 12_500_000.0
    assert row["pe_ratio"] == 18.5
    assert row["52_week_high"] is None  # bool refused; no invent
    assert row["52_week_low"] == 90.0
    assert row["previous_close"] == 100.0


def test_ai_validate_apply_yahoo_info_does_not_overwrite_present() -> None:
    row = {
        "volume": 1_000.0,
        "pe_ratio": 22.0,
        "52_week_high": 200.0,
        "52_week_low": 80.0,
        "previous_close": 150.0,
    }
    _ai_validate_apply_yahoo_info(
        row,
        {
            "volume": 99.0,
            "trailingPE": 1.0,
            "fiftyTwoWeekHigh": 999.0,
            "fiftyTwoWeekLow": 1.0,
            "previousClose": 2.0,
        },
    )
    assert row["volume"] == 1_000.0
    assert row["pe_ratio"] == 22.0
    assert row["52_week_high"] == 200.0
    assert row["52_week_low"] == 80.0
    assert row["previous_close"] == 150.0


def test_ai_validate_apply_yahoo_info_keeps_gaps_when_info_junk() -> None:
    row = {
        "volume": None,
        "pe_ratio": None,
        "52_week_high": None,
        "52_week_low": None,
        "previous_close": None,
    }
    _ai_validate_apply_yahoo_info(
        row,
        {
            "volume": True,
            "regularMarketVolume": False,
            "trailingPE": True,
            "forwardPE": None,
            "fiftyTwoWeekHigh": 0,
            "fiftyTwoWeekLow": -1,
            "previousClose": True,
        },
    )
    assert row["volume"] is None
    assert row["pe_ratio"] is None
    assert row["52_week_high"] is None
    assert row["52_week_low"] is None
    assert row["previous_close"] is None


def test_ai_validate_apply_yahoo_info_ignores_bad_shapes() -> None:
    row = {"volume": None}
    _ai_validate_apply_yahoo_info(row, None)  # type: ignore[arg-type]
    _ai_validate_apply_yahoo_info("x", {"volume": 1.0})  # type: ignore[arg-type]
    assert row["volume"] is None
