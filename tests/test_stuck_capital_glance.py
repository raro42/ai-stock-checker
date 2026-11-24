"""Stuck-capital glance (A15 / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    STUCK_CAPITAL_GLANCE_BIT_CAP,
    STUCK_CAPITAL_GLANCE_SYMBOLS_CAP,
    _coerce_stuck_capital_name_cap,
    build_stuck_capital_glance,
)


def test_stuck_capital_glance_empty() -> None:
    assert build_stuck_capital_glance(None)["ready"] is False
    assert build_stuck_capital_glance([])["ready"] is False
    assert build_stuck_capital_glance([{"unrealized_pct": -1}])["ready"] is False


def test_stuck_capital_glance_one() -> None:
    g = build_stuck_capital_glance(
        [{"symbol": "EXPE", "unrealized_pct": -3.2, "held": "1.2d"}]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["count"] == 1
    assert g["symbols"] == ["EXPE"]
    assert "1 past min-hold underwater" in g["line"]
    assert "EXPE -3.2%" in g["line"]


def test_stuck_capital_glance_refuses_bool_pct() -> None:
    """Bool/NaN unrealized_pct must not invent flat ±0.0% on the stuck line."""
    import math

    g = build_stuck_capital_glance(
        [
            {"symbol": "BOOL", "unrealized_pct": True, "held": "2d"},
            {"symbol": "NAN", "unrealized_pct": math.nan, "held": "2d"},
            {"symbol": "OK", "unrealized_pct": -2.5, "held": "2d"},
        ]
    )
    assert g["ready"] is True
    assert g["count"] == 3
    assert "BOOL n/a" in g["line"]
    assert "NAN n/a" in g["line"]
    assert "OK -2.5%" in g["line"]
    assert "+0.0%" not in g["line"]
    assert "True" not in g["line"]


def test_stuck_capital_glance_refuses_bool_name_cap() -> None:
    """True→1 must not invent a one-name A15 strip via rows[:True]."""
    assert (
        _coerce_stuck_capital_name_cap(True) == STUCK_CAPITAL_GLANCE_BIT_CAP
    )
    assert (
        _coerce_stuck_capital_name_cap(False) == STUCK_CAPITAL_GLANCE_BIT_CAP
    )
    assert _coerce_stuck_capital_name_cap(0) == STUCK_CAPITAL_GLANCE_BIT_CAP
    assert _coerce_stuck_capital_name_cap(None) == STUCK_CAPITAL_GLANCE_BIT_CAP
    assert _coerce_stuck_capital_name_cap(2) == 2
    assert (
        _coerce_stuck_capital_name_cap(
            True, default=STUCK_CAPITAL_GLANCE_SYMBOLS_CAP
        )
        == STUCK_CAPITAL_GLANCE_SYMBOLS_CAP
    )

    stuck = [
        {"symbol": f"S{i}", "unrealized_pct": -1.0 * (i + 1)} for i in range(5)
    ]
    g_true = build_stuck_capital_glance(stuck, bit_n=True, symbols_n=True)
    assert g_true["ready"] is True
    assert g_true["count"] == 5
    assert len(g_true["symbols"]) == STUCK_CAPITAL_GLANCE_SYMBOLS_CAP
    assert "S0 -1.0%" in g_true["line"]
    assert "S1 -2.0%" in g_true["line"]
    assert "S2 -3.0%" in g_true["line"]
    assert "+2 more" in g_true["line"]
    assert "S3" not in g_true["line"]
    # Without refuse, bit_n=True → rows[:1] + "+4 more".
    assert "+4 more" not in g_true["line"]

    g_false = build_stuck_capital_glance(stuck, bit_n=False, symbols_n=False)
    assert len(g_false["symbols"]) == STUCK_CAPITAL_GLANCE_SYMBOLS_CAP
    assert "S0 -1.0%" in g_false["line"]
    assert "+2 more" in g_false["line"]

    g_short = build_stuck_capital_glance(stuck, bit_n=2, symbols_n=2)
    assert g_short["symbols"] == ["S0", "S1"]
    assert "S0 -1.0%" in g_short["line"]
    assert "S1 -2.0%" in g_short["line"]
    assert "S2" not in g_short["line"]
    assert "+3 more" in g_short["line"]


def test_stuck_capital_glance_truncates_extra() -> None:
    stuck = [
        {"symbol": f"S{i}", "unrealized_pct": -1.0 * (i + 1)} for i in range(5)
    ]
    g = build_stuck_capital_glance(stuck)
    assert g["ready"] is True
    assert g["count"] == 5
    assert "S0 -1.0%" in g["line"]
    assert "S1 -2.0%" in g["line"]
    assert "S2 -3.0%" in g["line"]
    assert "+2 more" in g["line"]
    assert "S3" not in g["line"]
    assert len(g["line"]) <= 96


def test_stuck_capital_glance_line_cap() -> None:
    stuck = [
        {
            "symbol": "VERYLONGSYMBOLNAME",
            "unrealized_pct": -12.345,
        }
        for _ in range(4)
    ]
    g = build_stuck_capital_glance(stuck)
    assert g["ready"] is True
    assert len(g["line"]) <= 96
    assert g["line"].endswith("…") or len(g["line"]) < 96
