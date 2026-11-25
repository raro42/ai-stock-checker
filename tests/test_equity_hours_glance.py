"""US RTH vs Xetra equity-hours honesty glance (display only)."""

from __future__ import annotations

from datetime import datetime

import pytz

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    EQUITY_HOURS_LINE_CHARS,
    _HOURS_INACTIVE_QUIET_NAME_CAP,
    _clip_equity_hours_line,
    _coerce_equity_hours_line_chars,
    _coerce_hours_inactive_name_cap,
    _hours_inactive_venue_chip,
    build_equity_hours_glance,
    equity_hours_inactive_meta,
    load_desk_snapshot,
)


def test_equity_hours_inactive_meta_names_the_open() -> None:
    assert equity_hours_inactive_meta() == "closed"
    # Hot lean without venue list stays lean-only.
    assert (
        equity_hours_inactive_meta(
            attention_vs_open="align · hot|thin",
            attention_vs_open_warn=True,
            attention_all_cash=True,
        )
        == "align · hot|thin"
    )
    assert (
        equity_hours_inactive_meta(
            attention_vs_open="clash · attention hot · open strong",
            attention_vs_open_warn=True,
        )
        == "clash"
    )
    # Hot lean appends dark venues (Book matrix / Breadth chop warn inventory).
    assert (
        equity_hours_inactive_meta(
            attention_vs_open="align · hot|thin",
            attention_vs_open_warn=True,
            attention_all_cash=True,
            inactive_markets=["US", "Xetra"],
        )
        == "align · hot|thin · US · Xetra"
    )
    assert (
        equity_hours_inactive_meta(
            attention_vs_open="clash · attention hot · open strong",
            attention_vs_open_warn=True,
            inactive_markets=["US"],
        )
        == "clash · US"
    )
    assert (
        equity_hours_inactive_meta(
            attention_vs_open="align · hot|thin",
            attention_vs_open_warn=True,
            inactive_markets=["US", "Xetra", "A", "B", "C"],
        )
        == "align · hot|thin · US · Xetra · A · B · +1"
    )
    # Missing venue list still falls back to ownership labels.
    assert (
        equity_hours_inactive_meta(attention_all_cash=True) == "all cash"
    )
    assert (
        equity_hours_inactive_meta(attention_half_cash=True) == "half cash"
    )
    # Calm fold names dark venues (not bare half/all cash or a venue join).
    assert (
        equity_hours_inactive_meta(inactive_markets=["US", "Xetra"])
        == "quiet · 2 folds · US · Xetra"
    )
    assert (
        equity_hours_inactive_meta(
            attention_half_cash=True, inactive_markets=["US"]
        )
        == "quiet · 1 fold · US"
    )
    assert (
        equity_hours_inactive_meta(
            attention_all_cash=True, inactive_markets=["US", "Xetra"]
        )
        == "quiet · 2 folds · US · Xetra"
    )
    # Cap quiet names at 4 then +N (Close honesty / Policy honesty parity).
    assert (
        equity_hours_inactive_meta(
            inactive_markets=["US", "Xetra", "A", "B", "C"]
        )
        == "quiet · 5 folds · US · Xetra · A · B · +1"
    )


def test_hours_inactive_venue_chip_refuses_bool_name_cap() -> None:
    """True must not invent a one-venue dark chip (inventory name-cap peer)."""
    assert _coerce_hours_inactive_name_cap(True) == _HOURS_INACTIVE_QUIET_NAME_CAP
    assert _coerce_hours_inactive_name_cap(False) == _HOURS_INACTIVE_QUIET_NAME_CAP
    assert _coerce_hours_inactive_name_cap(0) == _HOURS_INACTIVE_QUIET_NAME_CAP
    assert _coerce_hours_inactive_name_cap(None) == _HOURS_INACTIVE_QUIET_NAME_CAP
    assert _coerce_hours_inactive_name_cap(2) == 2
    venues = ["US", "Xetra", "A", "B", "C"]
    # Bool cap falls back to 4 (+1), not names[:True] → one venue +4.
    assert (
        _hours_inactive_venue_chip(venues, quiet=True, cap=True)
        == "quiet · 5 folds · US · Xetra · A · B · +1"
    )
    assert (
        _hours_inactive_venue_chip(venues, quiet=False, cap=False)
        == "US · Xetra · A · B · +1"
    )
    assert (
        _hours_inactive_venue_chip(venues, quiet=False, cap=2)
        == "US · Xetra · +3"
    )


def test_coerce_equity_hours_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Hours strip; False must not wipe."""
    assert _coerce_equity_hours_line_chars(True) == EQUITY_HOURS_LINE_CHARS
    assert _coerce_equity_hours_line_chars(False) == EQUITY_HOURS_LINE_CHARS
    assert _coerce_equity_hours_line_chars(0) == EQUITY_HOURS_LINE_CHARS
    assert _coerce_equity_hours_line_chars(None) == EQUITY_HOURS_LINE_CHARS
    assert _coerce_equity_hours_line_chars(40) == 40


def test_clip_equity_hours_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > EQUITY_HOURS_LINE_CHARS
    default = _clip_equity_hours_line(long)
    assert len(default) == EQUITY_HOURS_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: EQUITY_HOURS_LINE_CHARS - 1] + "…"
    assert _clip_equity_hours_line(long, True) == default
    assert _clip_equity_hours_line(long, False) == default
    assert _clip_equity_hours_line(long, 0) == default
    thin = _clip_equity_hours_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_equity_hours_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    g_bool = build_equity_hours_glance(now=now, line_n=True)
    g_false = build_equity_hours_glance(now=now, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert g_bool["venue_chips_line"] == g["venue_chips_line"]
    assert g_false["inactive_line"] == g["inactive_line"]
    assert len(g["line"]) <= EQUITY_HOURS_LINE_CHARS
    g_short = build_equity_hours_glance(now=now, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")
    assert len(g_short["venue_chips_line"]) == 12
    assert g_short["venue_chips_line"].endswith("…")


def test_equity_hours_glance_both_open_us_morning() -> None:
    # Wednesday 10:00 ET ≈ both US RTH and Xetra open (Xetra until 17:30 Berlin).
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["us_open"] is True
    assert g["xetra_open"] is True
    # Silent open hid confirm — speak cash open (crypto out of denom).
    assert g["line"] == "active · US · Xetra · crypto · cash open"
    assert g["cash_open"] is True
    assert g["attention_line"] == ""
    assert g["attention_all_cash"] is False
    assert g["attention_half_cash"] is False
    assert g["attention_cash_share_pct"] is None
    assert g["attention_cash_share_severity"] == ""
    assert g["attention_open_count"] is None
    assert g["attention_open_share_pct"] is None
    assert g["attention_open_share_severity"] == ""
    assert g["attention_vs_open"] == ""
    assert g["attention_vs_open_warn"] is False
    assert g["inactive_line"] == ""
    assert g["inactive_meta"] == ""
    assert g["inactive_warn"] is False
    assert g["inactive_count"] == 0
    assert g["active_markets"] == ["US", "Xetra", "crypto"]
    assert g["inactive_markets"] == []
    assert g["venue_chips_line"] == (
        "cash · US open · Xetra open · crypto · on"
    )
    assert [c["id"] for c in g["venue_chips"]] == ["US", "Xetra", "crypto"]
    assert [c["status"] for c in g["venue_chips"]] == ["open", "open", "on"]


def test_equity_hours_glance_both_closed_weekend() -> None:
    sat = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 12, 12, 0))
    g = build_equity_hours_glance(now=sat)
    assert g["ready"] is True
    # Adverse hot|thin align escalates chip (session closed alone stayed flat).
    assert g["tone"] == "warn"
    assert g["us_open"] is False
    assert g["xetra_open"] is False
    # Lean owns the clip when extremes agree (hot|thin); vs-open stays in fields.
    assert g["line"] == (
        "active · crypto · attention · US · Xetra · all cash · "
        "attn vs open align · hot|thin"
    )
    assert g["attention_line"] == (
        "attention · US · Xetra · all cash · attn vs open align · hot|thin"
    )
    assert g["attention_all_cash"] is True
    assert g["attention_half_cash"] is False
    assert g["attention_cash_share_pct"] == 100
    assert g["attention_cash_share_severity"] == "hot"
    assert g["attention_open_count"] == 0
    assert g["attention_open_share_pct"] == 0
    assert g["attention_open_share_severity"] == "thin"
    assert g["attention_vs_open"] == "align · hot|thin"
    assert g["attention_vs_open_warn"] is True
    assert g["cash_open"] is False
    assert g["inactive_line"] == "Inactive markets (2): US · Xetra"
    assert g["inactive_meta"] == "align · hot|thin · US · Xetra"
    assert g["inactive_warn"] is True
    assert g["inactive_count"] == 2
    assert g["active_markets"] == ["crypto"]
    assert g["inactive_markets"] == ["US", "Xetra"]
    assert g["venue_chips_line"] == (
        "cash · US closed · Xetra closed · crypto · on"
    )
    assert [c["status"] for c in g["venue_chips"]] == [
        "closed",
        "closed",
        "on",
    ]


def test_equity_hours_glance_split_xetra_only() -> None:
    # 10:00 Berlin weekday: Xetra open; US still closed (04:00 ET).
    now = pytz.timezone("Europe/Berlin").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "split"
    assert g["xetra_open"] is True
    assert g["us_open"] is False
    # Half cash mid stays silent on lean; vs 1 open · 50% owns the clip.
    assert g["line"] == (
        "active · Xetra · crypto · attention · US · half cash · "
        "vs 1 open · 50%"
    )
    assert g["attention_line"] == (
        "attention · US · half cash · vs 1 open · 50%"
    )
    assert g["attention_all_cash"] is False
    assert g["attention_half_cash"] is True
    assert g["attention_cash_share_pct"] == 50
    assert g["attention_cash_share_severity"] == "ok"
    assert g["attention_open_count"] == 1
    assert g["attention_open_share_pct"] == 50
    assert g["attention_open_share_severity"] == "ok"
    assert g["attention_vs_open"] == ""
    assert g["attention_vs_open_warn"] is False
    assert g["cash_open"] is False
    assert g["inactive_line"] == "Inactive markets (1): US"
    assert g["inactive_meta"] == "quiet · 1 fold · US"
    assert g["inactive_warn"] is False
    assert g["inactive_count"] == 1
    assert g["active_markets"] == ["Xetra", "crypto"]
    assert g["inactive_markets"] == ["US"]
    assert g["venue_chips_line"] == (
        "cash · US closed · Xetra open · crypto · on"
    )
    assert g["venue_chips"][0]["status"] == "closed"
    assert g["venue_chips"][1]["status"] == "open"
    assert g["venue_chips"][2]["status"] == "on"


def test_equity_hours_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split", "warn"}
    assert g["line"].startswith("active · ")
    assert "crypto" in g["line"]
    assert "inactive_line" in g
    assert "inactive_meta" in g
    assert "inactive_warn" in g
    assert "inactive_count" in g
    assert "attention_all_cash" in g
    assert "attention_half_cash" in g
    assert "attention_cash_share_severity" in g
    assert "attention_open_count" in g
    assert "attention_open_share_pct" in g
    assert "attention_open_share_severity" in g
    assert "attention_vs_open" in g
    assert "attention_vs_open_warn" in g
    assert "cash_open" in g
    assert "venue_chips" in g
    assert "venue_chips_line" in g
    assert g["venue_chips_line"].startswith("cash · ")


def test_equity_hours_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split", "warn"}
    assert g["line"].startswith("active · ")
    assert "crypto" in g["line"]
    assert "inactive_line" in g
    assert "inactive_meta" in g
    assert "inactive_warn" in g
    assert "attention_all_cash" in g
    assert "attention_half_cash" in g
    assert "attention_cash_share_severity" in g
    assert "attention_open_count" in g
    assert "attention_open_share_pct" in g
    assert "attention_open_share_severity" in g
    assert "attention_vs_open" in g
    assert "attention_vs_open_warn" in g
    assert "cash_open" in g
    assert "venue_chips" in g
    assert "venue_chips_line" in g
    assert g["venue_chips_line"].startswith("cash · ")
