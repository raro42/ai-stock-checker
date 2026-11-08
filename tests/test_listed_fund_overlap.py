"""Same-theme ETF/ETC doubles on the open book (display only)."""

from __future__ import annotations

from stock_checker.listed_funds import (
    group_listed_fund_themes,
    listed_fund_theme,
    listed_fund_theme_overlaps,
)
from openbb_backend.desk import build_listed_fund_overlap_glance, load_desk_snapshot


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


def test_listed_fund_overlap_glance_share_hot() -> None:
    g = build_listed_fund_overlap_glance(["GLD", "4GLD.DE"])
    assert g["ready"] is True
    assert g["share_pct"] == 100
    assert g["share_severity"] == "hot"
    assert "hot · 100%" in g["line"]


def test_listed_fund_overlap_glance_share_quiet() -> None:
    book = ["GLD", "4GLD.DE", "AAPL", "MSFT", "NVDA", "META", "AMZN", "TSLA"]
    g = build_listed_fund_overlap_glance(book)
    assert g["ready"] is True
    assert g["n_book"] == 8
    assert g["n_overlap"] == 2
    assert g["share_pct"] == 25
    assert g["share_severity"] == "quiet"
    assert "quiet · 25%" in g["line"]


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


def test_listed_fund_overlap_in_chart_payload(tmp_path) -> None:
    from openbb_backend.charts import load_chart_payload

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 50000, "initial_cash": 100000, "holdings": '
        '{"SPY": 1, "SXR8.DE": 1}, "avg_buy_price": {"SPY": 400, '
        '"SXR8.DE": 500}, "total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["listed_fund_overlap_glance"]
    assert g["ready"] is True
    assert g["theme"] == "us_equity"
    assert "US equity" in g["line"]
