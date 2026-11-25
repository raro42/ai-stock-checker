"""Live book posture + next overweight trim glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    BOOK_POSTURE_LINE_CHARS,
    _clip_book_posture_line,
    _coerce_book_posture_line_chars,
    build_book_posture_glance,
    load_desk_snapshot,
)


def test_coerce_book_posture_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Posture strip; False must not wipe."""
    assert _coerce_book_posture_line_chars(True) == BOOK_POSTURE_LINE_CHARS
    assert _coerce_book_posture_line_chars(False) == BOOK_POSTURE_LINE_CHARS
    assert _coerce_book_posture_line_chars(0) == BOOK_POSTURE_LINE_CHARS
    assert _coerce_book_posture_line_chars(None) == BOOK_POSTURE_LINE_CHARS
    assert _coerce_book_posture_line_chars(40) == 40


def test_clip_book_posture_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > BOOK_POSTURE_LINE_CHARS
    default = _clip_book_posture_line(long)
    assert len(default) == BOOK_POSTURE_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: BOOK_POSTURE_LINE_CHARS - 1] + "…"
    assert _clip_book_posture_line(long, True) == default
    assert _clip_book_posture_line(long, False) == default
    assert _clip_book_posture_line(long, 0) == default
    thin = _clip_book_posture_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_book_posture_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_book_posture_glance([])
    g_bool = build_book_posture_glance([], line_n=True)
    g_false = build_book_posture_glance([], line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= BOOK_POSTURE_LINE_CHARS
    g_short = build_book_posture_glance([], line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_book_posture_glance_open_empty() -> None:
    g = build_book_posture_glance([])
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["posture"] == "open"
    assert g["modes"] == ("open", "at_cap", "overweight")
    assert g["overweight_scan_rotation"] is False
    assert g["overweight_new_buys"] is False
    assert "live open 0/5" in g["line"]
    assert "adds OK" in g["line"]


def test_book_posture_glance_at_cap() -> None:
    rows = [
        {"symbol": f"S{i}", "held_seconds": 100_000, "unrealized_pct": 1.0}
        for i in range(5)
    ]
    g = build_book_posture_glance(rows, max_positions=5)
    assert g["posture"] == "at_cap"
    assert g["tone"] == "at_cap"
    assert "live at_cap 5/5" in g["line"]
    assert "rotate OK" in g["line"]
    assert g["trim_symbol"] == ""


def test_book_posture_glance_overweight_next_trim_winner() -> None:
    hold = 100_000.0
    rows = [
        {"symbol": "LOSER", "held_seconds": hold, "unrealized_pct": -2.0},
        {"symbol": "WEAK", "held_seconds": hold, "unrealized_pct": 1.5},
        {"symbol": "STRONG", "held_seconds": hold, "unrealized_pct": 4.0},
        {"symbol": "A", "held_seconds": hold, "unrealized_pct": 0.5},
        {"symbol": "B", "held_seconds": hold, "unrealized_pct": -1.0},
        {"symbol": "C", "held_seconds": hold, "unrealized_pct": 2.0},
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    assert g["tone"] == "overweight"
    assert g["open_positions"] == 6
    assert g["trim_symbol"] == "A"
    assert "next trim A" in g["line"]
    assert "winner" in g["line"]


def test_book_posture_glance_refuses_bool_pct_for_trim() -> None:
    """Bool unrealized_pct must not invent True→+1% or flat 0% into trim pick."""
    hold = 100_000.0
    rows = [
        {"symbol": "BOOL", "held_seconds": hold, "unrealized_pct": True},
        {"symbol": "WEAK", "held_seconds": hold, "unrealized_pct": 0.5},
        {"symbol": "S2", "held_seconds": hold, "unrealized_pct": 2.0},
        {"symbol": "S3", "held_seconds": hold, "unrealized_pct": 3.0},
        {"symbol": "S4", "held_seconds": hold, "unrealized_pct": 4.0},
        {"symbol": "S5", "held_seconds": hold, "unrealized_pct": -1.0},
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    # True→1.0 would beat WEAK 0.5; inventing flat 0% would also distort ranking.
    assert g["trim_symbol"] == "WEAK"
    assert "BOOL" not in g["line"]


def test_book_posture_glance_bool_only_trim_paused() -> None:
    """All-bool marks → trim paused (not invent flat 0% worst-mark trim)."""
    hold = 100_000.0
    rows = [
        {"symbol": f"B{i}", "held_seconds": hold, "unrealized_pct": True}
        for i in range(6)
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    assert g["trim_symbol"] == ""
    assert "trim paused" in g["line"]


def test_book_posture_glance_refuses_bool_max_positions() -> None:
    """tradermonty #700/#655: True→1 slot must not invent at_cap 1/1."""
    rows = [
        {"symbol": "AAPL", "held_seconds": 100_000.0, "unrealized_pct": 1.0}
    ]
    g = build_book_posture_glance(rows, max_positions=True)  # type: ignore[arg-type]
    assert g["ready"] is True
    assert g["max_positions"] == 5
    assert g["posture"] == "open"
    assert "1/1" not in g["line"]
    assert "0/5" not in g["line"]
    assert "live open 1/5" in g["line"]
    g_off = build_book_posture_glance(rows, max_positions=False)  # type: ignore[arg-type]
    assert g_off["max_positions"] == 5
    assert g_off["posture"] == "open"


def test_book_posture_glance_overweight_trim_paused_min_hold() -> None:
    rows = [
        {"symbol": f"S{i}", "held_seconds": 60.0, "unrealized_pct": 3.0}
        for i in range(6)
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    assert g["trim_symbol"] == ""
    assert "trim paused" in g["line"]


def test_book_posture_glance_charts_skip_trim_guess() -> None:
    rows = [{"symbol": f"S{i}", "held_seconds": 0.0} for i in range(6)]
    g = build_book_posture_glance(rows, max_positions=5, suggest_trim=False)
    assert g["posture"] == "overweight"
    assert g["trim_symbol"] == ""
    assert "TP/SL+trim only" in g["line"]
    assert "next trim" not in g["line"]


def test_book_posture_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["book_posture_glance"]
    assert g["ready"] is True
    assert g["posture"] == "open"
    assert "live open" in g["line"]


def test_book_posture_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["book_posture_glance"]
    assert g["ready"] is True
    assert g["posture"] == "open"
    assert "live open" in g["line"]
