"""Largest-name vs entry concentration cap glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_concentration_glance, load_desk_snapshot


def test_concentration_glance_empty_input() -> None:
    assert build_concentration_glance(None)["ready"] is False
    assert build_concentration_glance("x")["ready"] is False  # type: ignore[arg-type]


def test_concentration_glance_cap_off() -> None:
    g = build_concentration_glance(
        {"largest_symbol": "AAPL", "largest_pct": 10.0},
        max_name_pct=0,
    )
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


def test_concentration_glance_no_names() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "",
            "largest_pct": 0.0,
            "concentration_warn": False,
            "posture": "open",
            "slots": "0/5",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["warn"] is False
    assert "no open names" in g["line"]
    assert "30%" in g["line"]
    assert g["headroom_pp"] == 30.0


def test_concentration_glance_headroom() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "aapl",
            "largest_pct": 18.0,
            "concentration_warn": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["symbol"] == "AAPL"
    assert g["warn"] is False
    assert g["headroom_pp"] == 12.0
    assert "AAPL" in g["line"]
    assert "12pp headroom" in g["line"]


def test_concentration_glance_warn() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "JPM",
            "largest_pct": 40.0,
            "concentration_warn": True,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["warn"] is True
    assert "WARN" in g["line"]
    assert "JPM" in g["line"]
    assert "30%" in g["line"]
    assert g["headroom_pp"] == 0.0


def test_concentration_glance_refuses_bool_and_nan() -> None:
    """Bool/NaN largest_pct must not invent flat 0% / True→1% headroom."""
    import math

    for bad in (True, False, math.nan, "12", -1.0):
        g = build_concentration_glance(
            {"largest_symbol": "AAPL", "largest_pct": bad, "concentration_warn": False}
        )
        assert g["ready"] is True
        assert g["tone"] == "warn"
        assert g["warn"] is True
        assert g["largest_pct"] is None
        assert g["headroom_pp"] is None
        assert "n/a" in g["line"]
        assert "unreadable" in g["line"]
        assert "AAPL" in g["line"]


def test_concentration_glance_refuses_bool_cap_and_open_count() -> None:
    """tradermonty #700/#655: True→1% cap / False→off / True→1 open invent."""
    # Bool cap → default 30% (not invent 1% WARN or off).
    g = build_concentration_glance(
        {"largest_symbol": "AAPL", "largest_pct": 18.0},
        max_name_pct=True,  # type: ignore[arg-type]
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["cap_pct"] == 30.0
    assert "30%" in g["line"]
    g_off = build_concentration_glance(
        {"largest_symbol": "AAPL", "largest_pct": 18.0},
        max_name_pct=False,  # type: ignore[arg-type]
    )
    assert g_off["ready"] is True
    assert g_off["tone"] == "clear"
    assert g_off["cap_pct"] == 30.0
    assert "off" not in g_off["line"]
    # Bool open_positions alone → empty book (not invent mv unreadable).
    g_open = build_concentration_glance(
        {
            "largest_symbol": "",
            "largest_pct": None,
            "open_positions": True,
            "concentration_warn": False,
        }
    )
    assert g_open["ready"] is True
    assert g_open["tone"] == "clear"
    assert "no open names" in g_open["line"]
    assert "mv unreadable" not in g_open["line"]


def test_concentration_glance_open_lots_mv_unreadable() -> None:
    """Open slots with no readable MV ≠ empty-book 'no open names'."""
    g = build_concentration_glance(
        {
            "largest_symbol": "",
            "largest_pct": None,
            "open_positions": 2,
            "concentration_warn": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["warn"] is True
    assert g["largest_pct"] is None
    assert "mv unreadable" in g["line"]
    assert "no open names" not in g["line"]


def test_concentration_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["concentration_glance"]
    assert g["ready"] is True
    assert "cap" in g["line"].lower() or "30%" in g["line"]


def test_concentration_glance_in_chart_payload(tmp_path) -> None:
    from openbb_backend.charts import load_chart_payload

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["concentration_glance"]
    assert g["ready"] is True
    assert "cap" in g["line"].lower() or "30%" in g["line"]
