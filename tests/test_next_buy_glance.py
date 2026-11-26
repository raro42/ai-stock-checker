"""Next-buy sizer glance (tradermonty / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    NEXT_BUY_LINE_CHARS,
    _clip_next_buy_line,
    _coerce_next_buy_line_chars,
    build_next_buy_glance,
)


def test_next_buy_glance_empty() -> None:
    assert build_next_buy_glance(None)["ready"] is False
    assert build_next_buy_glance({})["ready"] is False
    assert build_next_buy_glance({"eur": 100})["ready"] is False


def test_next_buy_glance_open() -> None:
    g = build_next_buy_glance(
        {
            "eur": 7610.0,
            "cash_frac": 0.1,
            "slots_open": 2,
            "capped_by": "cash_frac",
            "note": "~10% of cash (2 slots open)",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["eur"] == 7610.0
    assert g["slots_open"] == 2
    assert "Next buy ~€7,610" in g["line"]
    assert "2 slots open" in g["line"]


def test_next_buy_glance_concentration_warn() -> None:
    g = build_next_buy_glance(
        {
            "eur": 500.0,
            "slots_open": 1,
            "capped_by": "concentration",
            "note": "~10% cash · capped at 30% equity",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "Next buy ~€500" in g["line"]


def test_next_buy_glance_book_full() -> None:
    g = build_next_buy_glance(
        {
            "eur": 0.0,
            "slots_open": 0,
            "capped_by": "book_full",
            "note": "book full (5/5)",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["line"].startswith("No new buy")
    assert "book full" in g["line"]


def test_next_buy_glance_line_cap() -> None:
    g = build_next_buy_glance(
        {
            "eur": 1.0,
            "slots_open": 1,
            "capped_by": "cash_frac",
            "note": "x" * 120,
        }
    )
    assert g["ready"] is True
    assert len(g["line"]) <= NEXT_BUY_LINE_CHARS
    assert g["line"].endswith("…")


def test_clip_next_buy_line_refuses_bool_ceiling() -> None:
    """True→1 / False→0 must not invent a one-char strip or wipe."""
    long = "x" * 120
    assert len(long) > NEXT_BUY_LINE_CHARS
    default = _clip_next_buy_line(long)
    assert len(default) == NEXT_BUY_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: NEXT_BUY_LINE_CHARS - 1] + "…"
    assert _clip_next_buy_line(long, True) == default
    assert _clip_next_buy_line(long, False) == default
    assert _clip_next_buy_line(long, 0) == default
    assert _coerce_next_buy_line_chars(True) == NEXT_BUY_LINE_CHARS
    assert _coerce_next_buy_line_chars(False) == NEXT_BUY_LINE_CHARS
    thin = _clip_next_buy_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_next_buy_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    payload = {
        "eur": 1.0,
        "slots_open": 1,
        "capped_by": "cash_frac",
        "note": "x" * 120,
    }
    g = build_next_buy_glance(payload)
    g_bool = build_next_buy_glance(payload, line_n=True)
    g_false = build_next_buy_glance(payload, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= NEXT_BUY_LINE_CHARS
    assert g["line"].startswith("Next buy")
    thin = build_next_buy_glance(payload, line_n=12)
    assert len(thin["line"]) == 12
    assert thin["line"].endswith("…")


def test_next_buy_glance_refuses_bool_eur() -> None:
    """tradermonty #700/#655: True→€1 must not invent a next-buy line."""
    g = build_next_buy_glance(
        {
            "eur": True,
            "slots_open": True,
            "capped_by": "cash_frac",
            "note": "~10% of cash",
        }
    )
    assert g["ready"] is True
    assert g["eur"] == 0.0
    assert g["slots_open"] == 0
    assert g["line"].startswith("No new buy")
