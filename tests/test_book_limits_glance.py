"""Book limits + fee schedule glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    BOOK_LIMITS_LINE_CHARS,
    _clip_book_limits_line,
    _coerce_book_limits_line_chars,
    build_book_limits_glance,
)


def test_book_limits_glance_empty() -> None:
    assert build_book_limits_glance(None)["ready"] is False
    assert build_book_limits_glance({})["ready"] is False
    assert build_book_limits_glance({"max_positions": 5})["ready"] is False


def test_book_limits_glance_refuses_bool_slots_hold() -> None:
    """tradermonty #700/#655: True→1 slot / True→1h must not invent packaging."""
    assert (
        build_book_limits_glance(
            {
                "max_positions": True,
                "min_hold_hours": 24,
                "fee_preset": "revolut_standard",
            }
        )["ready"]
        is False
    )
    assert (
        build_book_limits_glance(
            {
                "max_positions": 5,
                "min_hold_hours": True,
                "fee_preset": "revolut_standard",
            }
        )["ready"]
        is False
    )
    assert (
        build_book_limits_glance(
            {
                "max_positions": False,
                "min_hold_hours": False,
                "fee_preset": "revolut_standard",
            }
        )["ready"]
        is False
    )


def test_book_limits_glance_defaults() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "book"
    assert g["max_positions"] == 5
    assert g["min_hold_hours"] == 24.0
    assert g["fee_preset"] == "revolut_standard"
    assert "5 slots" in g["line"]
    assert "≥24h hold" in g["line"] or ">=24h hold" in g["line"]
    assert "Revolut Std" in g["line"]
    assert "0.25%" in g["line"]
    assert len(g["line"]) <= BOOK_LIMITS_LINE_CHARS


def test_book_limits_glance_warn_short_hold() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 2,
            "fee_preset": "revolut_standard",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "≥2h hold" in g["line"] or ">=2h hold" in g["line"]


def test_book_limits_glance_optimistic_spot_fees() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "binance_like",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "optimistic"
    assert "Spot-like" in g["line"]


def test_clip_book_limits_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > BOOK_LIMITS_LINE_CHARS
    default = _clip_book_limits_line(long)
    assert len(default) == BOOK_LIMITS_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: BOOK_LIMITS_LINE_CHARS - 1] + "…"
    assert _clip_book_limits_line(long, True) == default
    assert _clip_book_limits_line(long, False) == default
    assert _clip_book_limits_line(long, 0) == default
    assert _coerce_book_limits_line_chars(True) == BOOK_LIMITS_LINE_CHARS
    assert _coerce_book_limits_line_chars(False) == BOOK_LIMITS_LINE_CHARS
    thin = _clip_book_limits_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_book_limits_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    runtime = {
        "max_positions": 5,
        "min_hold_hours": 24,
        "fee_preset": "revolut_standard",
    }
    g = build_book_limits_glance(runtime)
    g_bool = build_book_limits_glance(runtime, line_n=True)
    g_false = build_book_limits_glance(runtime, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= BOOK_LIMITS_LINE_CHARS
    g_short = build_book_limits_glance(runtime, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_book_limits_glance_in_chart_payload(tmp_path) -> None:
    payload = load_chart_payload(tmp_path)
    g = payload["book_limits_glance"]
    assert g["ready"] is True
    assert g["max_positions"] >= 1
    assert "slots" in g["line"]
