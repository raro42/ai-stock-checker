"""Entry score band + interleave honesty glance (A11; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    ENTRY_SLOTS_LINE_CHARS,
    _clip_entry_slots_line,
    _coerce_entry_slots_line_chars,
    build_entry_slots_glance,
    load_desk_snapshot,
)
from stock_checker.entry_slots import (
    DEFAULT_MAX_CRYPTO_SLOTS,
    DEFAULT_MAX_STOCK_SLOTS,
    STOCK_BREAKOUT_SCORE_BASE,
)


def test_coerce_entry_slots_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Slots strip; False must not wipe."""
    assert _coerce_entry_slots_line_chars(True) == ENTRY_SLOTS_LINE_CHARS
    assert _coerce_entry_slots_line_chars(False) == ENTRY_SLOTS_LINE_CHARS
    assert _coerce_entry_slots_line_chars(0) == ENTRY_SLOTS_LINE_CHARS
    assert _coerce_entry_slots_line_chars(None) == ENTRY_SLOTS_LINE_CHARS
    assert _coerce_entry_slots_line_chars(40) == 40


def test_clip_entry_slots_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > ENTRY_SLOTS_LINE_CHARS
    default = _clip_entry_slots_line(long)
    assert len(default) == ENTRY_SLOTS_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: ENTRY_SLOTS_LINE_CHARS - 1] + "…"
    assert _clip_entry_slots_line(long, True) == default
    assert _clip_entry_slots_line(long, False) == default
    assert _clip_entry_slots_line(long, 0) == default
    thin = _clip_entry_slots_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_entry_slots_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_entry_slots_glance()
    g_bool = build_entry_slots_glance(line_n=True)
    g_false = build_entry_slots_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= ENTRY_SLOTS_LINE_CHARS
    g_short = build_entry_slots_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_entry_slots_glance_ready() -> None:
    g = build_entry_slots_glance()
    assert g["ready"] is True
    assert g["tone"] == "slots"
    assert g["pure_global_sort"] is False
    assert g["score_base"] == float(STOCK_BREAKOUT_SCORE_BASE)
    assert g["max_crypto_slots"] == int(DEFAULT_MAX_CRYPTO_SLOTS)
    assert g["max_stock_slots"] == int(DEFAULT_MAX_STOCK_SLOTS)
    assert "pct_from_high" in g["line"]
    assert "interleave" in g["line"]
    assert "not pure sort" in g["line"]
    assert f"{STOCK_BREAKOUT_SCORE_BASE:g}+" in g["line"]


def test_entry_slots_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["entry_slots_glance"]
    assert g["ready"] is True
    assert g["pure_global_sort"] is False
    assert "interleave" in g["line"]


def test_entry_slots_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["entry_slots_glance"]
    assert g["ready"] is True
    assert g["pure_global_sort"] is False
    assert "pct_from_high" in g["line"]
