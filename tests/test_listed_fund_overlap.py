"""Same-theme ETF/ETC doubles on the open book (display only)."""

from __future__ import annotations

from stock_checker.listed_funds import (
    group_listed_fund_themes,
    listed_fund_theme,
    listed_fund_theme_overlaps,
)
from openbb_backend.desk import (
    build_listed_fund_overlap_glance,
    listed_fund_overlap_lean_meta,
    listed_fund_overlap_vs_conc,
    listed_fund_overlap_vs_other_lead,
    listed_fund_overlap_vs_other_sample_gap,
    load_desk_snapshot,
)


def test_listed_fund_themes() -> None:
    assert listed_fund_theme("GLD") == "gold"
    assert listed_fund_theme("4gld.de") == "gold"
    assert listed_fund_theme("SPY") == "us_equity"
    assert listed_fund_theme("SXR8.DE") == "us_equity"
    assert listed_fund_theme("VWCE.DE") == "world_equity"
    assert listed_fund_theme("AAPL") == ""


def test_listed_fund_theme_overlaps() -> None:
    assert listed_fund_theme_overlaps(["GLD", "AAPL"]) == []
    assert listed_fund_theme_overlaps(["GLD", "4GLD.DE"]) == [
        ("gold", ["GLD", "4GLD.DE"])
    ]
    groups = group_listed_fund_themes(["SPY", "SXR8.DE", "GLD", "4GLD.DE"])
    assert set(groups) == {"us_equity", "gold"}
    overlaps = listed_fund_theme_overlaps(
        ["SPY", "SXR8.DE", "GLD", "4GLD.DE", "VWCE.DE"]
    )
    assert overlaps[0][0] in {"us_equity", "gold"}
    assert len(overlaps) == 2


def test_listed_fund_overlap_glance_silent() -> None:
    assert build_listed_fund_overlap_glance(None)["ready"] is False
    assert build_listed_fund_overlap_glance([])["ready"] is False
    assert build_listed_fund_overlap_glance(
        [{"symbol": "GLD"}, {"symbol": "AAPL"}]
    )["ready"] is False
    assert build_listed_fund_overlap_glance(
        [{"symbol": "SPY"}, {"symbol": "VWCE.DE"}]
    )["ready"] is False


def test_listed_fund_overlap_vs_other_lead_helpers() -> None:
    bit, name, pct = listed_fund_overlap_vs_other_lead(2, 3)
    assert bit == "lead other · 60%"
    assert name == "other"
    assert pct == 60
    assert listed_fund_overlap_vs_other_sample_gap(2, 3) == ""
    bit, name, pct = listed_fund_overlap_vs_other_lead(3, 2)
    assert bit == "lead overlap · 60%"
    assert name == "overlap"
    assert pct == 60
    assert listed_fund_overlap_vs_other_lead(2, 2) == ("", "", None)
    assert listed_fund_overlap_vs_other_sample_gap(2, 2) == "overlap/other tied"
    assert listed_fund_overlap_vs_other_lead(2, 0) == ("", "", None)
    assert listed_fund_overlap_vs_other_sample_gap(2, 0) == ""


def test_listed_fund_overlap_vs_conc() -> None:
    bit, warn = listed_fund_overlap_vs_conc("hot", False)
    assert bit == "clash · funds hot · Conc clear"
    assert warn is True
    bit, warn = listed_fund_overlap_vs_conc("hot", True)
    assert bit == "align · funds hot · Conc warn"
    assert warn is False
    bit, warn = listed_fund_overlap_vs_conc("quiet", True)
    assert bit == "clash · funds quiet · Conc warn"
    assert warn is True
    bit, warn = listed_fund_overlap_vs_conc("quiet", False)
    assert bit == "align · funds quiet · Conc clear"
    assert warn is False
    assert listed_fund_overlap_vs_conc("", False) == ("", False)
    assert listed_fund_overlap_vs_conc("hot", None) == ("", False)
    assert listed_fund_overlap_vs_conc("mid", False) == ("", False)


def test_listed_fund_overlap_lean_meta() -> None:
    assert listed_fund_overlap_lean_meta("") == "quiet"
    quiet = listed_fund_overlap_lean_meta(
        "vs 3 other · 60% · lead other · 60%"
    )
    assert quiet.startswith("quiet")
    assert "vs other" in quiet
    assert "other" in quiet
    warn = listed_fund_overlap_lean_meta(
        "vs 0 other · thin · 0%", warn=True
    )
    assert warn.startswith("warn")
    assert "vs other" in warn
    conc = listed_fund_overlap_lean_meta(
        "clash · funds hot · Conc clear", warn=True
    )
    assert conc.startswith("warn")
    assert "Conc" in conc


def test_listed_fund_overlap_glance_warn() -> None:
    g = build_listed_fund_overlap_glance(
        [
            {"symbol": "gld"},
            {"symbol": "4GLD.DE"},
            {"symbol": "AAPL"},
            {"symbol": "MSFT"},
            {"symbol": "NVDA"},
        ]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["warn"] is True
    assert g["theme"] == "gold"
    assert g["count"] == 2
    assert "2 gold" in g["line"]
    assert "GLD" in g["line"]
    assert "4GLD.DE" in g["line"]
    # 2 of 5 names → mid band shows % only (count ≠ share).
    assert g["n_book"] == 5
    assert g["n_overlap"] == 2
    assert g["share_pct"] == 40
    assert g["share_severity"] == ""
    assert "40%" in g["line"]
    # Strip keeps theme + share; vs-other / lead sit in lean fold.
    assert "vs 3 other" not in g["line"]
    assert g["bit_core"] == g["line"]
    assert g["n_other"] == 3
    assert g["other_share_pct"] == 60
    assert g["other_share_severity"] == ""
    assert "vs 3 other · 60%" in g["lean"]
    assert g["vs_other_lead"] == "lead other · 60%"
    assert g["vs_other_lead_name"] == "other"
    assert g["vs_other_lead_pct"] == 60
    assert g["vs_other_sample_gap"] == ""
    assert "lead other · 60%" in g["lean"]
    assert "vs 3 other · 60% · lead other · 60%" in g["bit"]
    assert g["lean_warn"] is True
    assert g["lean_meta"].startswith("warn")


def test_listed_fund_overlap_glance_share_hot() -> None:
    g = build_listed_fund_overlap_glance(["GLD", "4GLD.DE"])
    assert g["ready"] is True
    assert g["share_pct"] == 100
    assert g["share_severity"] == "hot"
    assert "hot · 100%" in g["line"]
    assert g["n_other"] == 0
    assert g["other_share_pct"] == 0
    assert g["other_share_severity"] == "thin"
    assert "vs 0 other · thin · 0%" in g["lean"]
    assert "vs 0 other" not in g["line"]
    # Sole-side (all overlap) stays silent on ownership lead.
    assert g["vs_other_lead"] == ""
    assert g["vs_other_sample_gap"] == ""
    # Unknown Conc stays silent.
    assert g["vs_conc"] == ""
    assert g["concentration_warn"] is None


def test_listed_fund_overlap_glance_vs_conc_clash() -> None:
    g = build_listed_fund_overlap_glance(
        ["GLD", "4GLD.DE"], concentration_warn=False
    )
    assert g["ready"] is True
    assert g["share_severity"] == "hot"
    assert g["vs_conc"] == "clash · funds hot · Conc clear"
    assert g["vs_conc_warn"] is True
    assert "clash · funds hot · Conc clear" in g["lean"]
    assert "Conc clear" not in g["line"]
    assert "Conc" in g["lean_meta"]
    align = build_listed_fund_overlap_glance(
        ["GLD", "4GLD.DE"], concentration_warn=True
    )
    assert align["vs_conc"] == "align · funds hot · Conc warn"
    assert align["vs_conc_warn"] is False
    # Mid share stays silent on Conc even when Conc is known.
    mid = build_listed_fund_overlap_glance(
        [
            {"symbol": "GLD"},
            {"symbol": "4GLD.DE"},
            {"symbol": "AAPL"},
            {"symbol": "MSFT"},
            {"symbol": "NVDA"},
        ],
        concentration_warn=False,
    )
    assert mid["share_severity"] == ""
    assert mid["vs_conc"] == ""


def test_listed_fund_overlap_glance_share_quiet() -> None:
    book = ["GLD", "4GLD.DE", "AAPL", "MSFT", "NVDA", "META", "AMZN", "TSLA"]
    g = build_listed_fund_overlap_glance(book)
    assert g["ready"] is True
    assert g["n_book"] == 8
    assert g["n_overlap"] == 2
    assert g["share_pct"] == 25
    assert g["share_severity"] == "quiet"
    assert "quiet · 25%" in g["line"]
    assert g["n_other"] == 6
    assert g["other_share_pct"] == 75
    assert g["other_share_severity"] == "strong"
    assert "vs 6 other · strong · 75%" in g["lean"]
    assert g["vs_other_lead"] == "lead other · 75%"
    assert g["vs_other_lead_name"] == "other"
    assert "lead other · 75%" in g["lean"]
    assert "lead other" not in g["line"]


def test_listed_fund_overlap_glance_vs_other_tied() -> None:
    g = build_listed_fund_overlap_glance(
        ["GLD", "4GLD.DE", "AAPL", "MSFT"]
    )
    assert g["ready"] is True
    assert g["n_overlap"] == 2
    assert g["n_other"] == 2
    assert g["vs_other_lead"] == ""
    assert g["vs_other_sample_gap"] == "overlap/other tied"
    assert "overlap/other tied" in g["lean"]
    assert "overlap/other tied" not in g["line"]


def test_listed_fund_overlap_glance_multi_theme() -> None:
    g = build_listed_fund_overlap_glance(
        ["SPY", "SXR8.DE", "GLD", "4GLD.DE"]
    )
    assert g["ready"] is True
    assert "US equity" in g["line"]
    assert "gold" in g["line"]
    assert set(g["themes"]) == {"us_equity", "gold"}
    assert g["n_overlap"] == 4
    assert g["share_pct"] == 100
    assert g["share_severity"] == "hot"
    assert "hot · 100%" in g["line"]
    assert g["n_other"] == 0
    assert g["other_share_severity"] == "thin"
    assert "vs 0 other · thin · 0%" in g["lean"]
    assert g["vs_other_lead"] == ""
    assert g["vs_other_sample_gap"] == ""


def test_listed_fund_overlap_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 50000, "initial_cash": 100000, "holdings": '
        '{"GLD": 10, "4GLD.DE": 5}, "avg_buy_price": {"GLD": 180, '
        '"4GLD.DE": 50}, "total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["listed_fund_overlap_glance"]
    assert g["ready"] is True
    assert g["theme"] == "gold"
    assert "GLD" in g["line"]
    # Hot theme share + Conc clear (small lots vs cash) → clash under lean.
    assert g["share_severity"] == "hot"
    assert snap["concentration_glance"]["warn"] is False
    assert g["vs_conc"] == "clash · funds hot · Conc clear"
    assert "clash · funds hot · Conc clear" in g["lean"]


def test_listed_fund_overlap_in_chart_payload(tmp_path) -> None:
    from openbb_backend.charts import load_chart_payload

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 50000, "initial_cash": 100000, "holdings": '
        '{"SPY": 1, "SXR8.DE": 1}, "avg_buy_price": {"SPY": 400, '
        '"SXR8.DE": 500}, "total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    payload = load_chart_payload(tmp_path)
    g = payload["listed_fund_overlap_glance"]
    assert g["ready"] is True
    assert g["theme"] == "us_equity"
    assert "US equity" in g["line"]
    assert g["share_severity"] == "hot"
    assert payload["concentration_glance"]["warn"] is False
    assert g["vs_conc"] == "clash · funds hot · Conc clear"
