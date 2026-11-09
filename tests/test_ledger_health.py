"""Ledger shard honesty (display only; not a gate)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.charts import _load_jsonl
from openbb_backend.desk import (
    build_ledger_health,
    ledger_short_lean_meta,
    ledger_short_vs_long_lead,
    ledger_short_vs_long_lead_size,
    ledger_short_vs_long_lean,
    ledger_short_vs_long_sample_gap,
    load_json_checked,
    load_jsonl_checked,
)


def test_ledger_health_silent_when_no_files(tmp_path: Path) -> None:
    g = build_ledger_health(tmp_path)
    assert g["ready"] is False
    assert g["line"] == ""


def test_ledger_ok(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text("{}")
    (tmp_path / "trades.jsonl").write_text('{"type":"BUY","symbol":"AAPL"}\n')
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "ok"
    assert g["tone"] == "ok"
    assert g["line"] == "ledger ok"
    assert g["good_lines"] == 1
    assert g["bad_lines"] == 0


def test_ledger_keeps_good_rows_and_names_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "trades.jsonl"
    path.write_text('{"type":"BUY"}\nnot-json\n{"type":"SELL"}\n')
    rows, meta = load_jsonl_checked(path)
    assert [r["type"] for r in rows] == ["BUY", "SELL"]
    assert meta["state"] == "thin"
    assert meta["bad"] == 1
    (tmp_path / "portfolio.json").write_text('{"cash": 1}')
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "thin"
    assert g["tone"] == "warn"
    assert g["line"] == "ledger thin · 1 bad line"
    assert g["good_lines"] == 2
    assert _load_jsonl(path) == rows


def test_ledger_bad_portfolio_and_trades(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text("{")
    (tmp_path / "trades.jsonl").write_text("nope\n")
    doc, meta = load_json_checked(tmp_path / "portfolio.json", {})
    assert doc == {}
    assert meta["state"] == "malformed"
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "bad"
    assert g["line"] == "ledger bad · portfolio malformed · trades malformed"
    assert g["good_lines"] == 0


def test_ledger_non_object_portfolio_is_bad(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text("[1]")
    doc, meta = load_json_checked(tmp_path / "portfolio.json", {})
    assert doc == {}
    assert meta["state"] == "malformed"
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "bad"
    assert "portfolio malformed" in g["line"]


def test_load_json_checked_lean_type_mismatch(tmp_path: Path) -> None:
    """xang1234 #498/#540: parseable wrong container → lean malformed, not ok."""
    path = tmp_path / "row.json"
    path.write_text('["not", "an", "object"]')
    doc, meta = load_json_checked(path, {})
    assert doc == {}
    assert meta["state"] == "malformed"
    assert meta["bad"] == 1

    path.write_text('{"a": 1}')
    doc, meta = load_json_checked(path, [])
    assert doc == []
    assert meta["state"] == "malformed"

    path.write_text("null")
    doc, meta = load_json_checked(path, {})
    assert doc == {}
    assert meta["state"] == "malformed"

    path.write_text('{"ok": true}')
    doc, meta = load_json_checked(path, {})
    assert doc == {"ok": True}
    assert meta["state"] == "ok"


def test_ledger_missing_portfolio_with_fills_is_thin(tmp_path: Path) -> None:
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "thin"
    assert g["line"] == "ledger thin · no portfolio"


def test_ledger_short_holdings_refuse(tmp_path: Path) -> None:
    """tradermonty #681: non-positive holdings → short refuse on ledger glance."""
    import json

    (tmp_path / "portfolio.json").write_text(
        json.dumps({"cash": 1000, "holdings": {"AAPL": 10, "TSLA": -3, "ZERO": 0}})
    )
    (tmp_path / "trades.jsonl").write_text('{"type":"BUY","symbol":"AAPL"}\n')
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "bad"
    assert g["tone"] == "warn"
    assert g["short_count"] == 2
    assert g["short_symbols"] == ["TSLA", "ZERO"]
    assert "2 short refuse" in g["line"]
    assert "TSLA" in g["line"]
    # 2 of 3 names → hot share (count ≠ share).
    assert g["n_book"] == 3
    assert g["short_share_pct"] == 67
    assert g["short_share_severity"] == "hot"
    assert "hot · 67%" in g["line"]
    # 1 long of 3 → thin vs-long under lean (not on primary line).
    assert g["n_long"] == 1
    assert g["long_share_pct"] == 33
    assert g["long_share_severity"] == "thin"
    assert "vs 1 long · thin · 33%" in g["lean"]
    assert g["vs_long_lead"] == "lead short · 67%"
    assert g["vs_long_lead_name"] == "short"
    assert g["vs_long_lead_pct"] == 67
    assert g["vs_long_sample_gap"] == ""
    assert "lead short · 67%" in g["lean"]
    # 2 short vs 1 long → lead size 2× (name/% ≠ magnitude).
    assert g["vs_long_lead_size"] == 2.0
    assert g["vs_long_lead_size_louder"] == 2
    assert g["vs_long_lead_size_quieter"] == 1
    assert "lead size · 2×" in g["lean"]
    assert "lead size sides · louder 2 · quieter 1" in g["lean"]
    assert "lead size" not in g["line"]
    assert "vs 1 long" not in g["line"]
    assert "vs 1 long" in g["bit"]
    assert g["lean_warn"] is True
    assert "vs long" in g["lean_meta"]
    assert "short" in g["lean_meta"]
    assert "size" in g["lean_meta"]
    assert "sides" in g["lean_meta"]


def test_ledger_short_refuse_share_quiet(tmp_path: Path) -> None:
    """Quiet share when shorts are a small slice of the holding map."""
    import json

    holdings = {"TSLA": -1, "ZERO": 0}
    for i, sym in enumerate(
        ["AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOG"]
    ):
        holdings[sym] = float(i + 1)
    (tmp_path / "portfolio.json").write_text(
        json.dumps({"cash": 1000, "holdings": holdings})
    )
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["short_count"] == 2
    assert g["n_book"] == 8
    assert g["short_share_pct"] == 25
    assert g["short_share_severity"] == "quiet"
    assert "quiet · 25%" in g["line"]
    assert "2 short refuse" in g["line"]
    # 6 long of 8 → strong; lean closed (not warn); long owns the map.
    assert g["n_long"] == 6
    assert g["long_share_pct"] == 75
    assert g["long_share_severity"] == "strong"
    assert "vs 6 long · strong · 75%" in g["lean"]
    assert g["vs_long_lead"] == "lead long · 75%"
    assert g["vs_long_lead_name"] == "long"
    assert g["vs_long_lead_pct"] == 75
    assert "lead long · 75%" in g["lean"]
    # 6 long vs 2 short → lead size 3×.
    assert g["vs_long_lead_size"] == 3.0
    assert g["vs_long_lead_size_louder"] == 6
    assert g["vs_long_lead_size_quieter"] == 2
    assert "lead size · 3×" in g["lean"]
    assert "lead size sides · louder 6 · quieter 2" in g["lean"]
    # quiet short + strong long → severity align (not clash).
    assert g["vs_long_lean"] == "short vs long align · quiet|strong"
    assert g["vs_long_lean_warn"] is False
    assert "short vs long align · quiet|strong" in g["lean"]
    assert "vs 6 long" not in g["line"]
    assert g["lean_warn"] is False
    assert g["lean_meta"].startswith("quiet")
    assert "long" in g["lean_meta"]
    assert "size" in g["lean_meta"]
    assert "align" in g["lean_meta"]


def test_ledger_short_refuse_share_mid(tmp_path: Path) -> None:
    """Mid band shows % only (not hot/quiet)."""
    import json

    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "cash": 1000,
                "holdings": {
                    "TSLA": -1,
                    "ZERO": 0,
                    "AAPL": 1,
                    "MSFT": 1,
                    "NVDA": 1,
                },
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["short_count"] == 2
    assert g["n_book"] == 5
    assert g["short_share_pct"] == 40
    assert g["short_share_severity"] == ""
    assert "40%" in g["line"]
    assert "hot" not in g["line"]
    assert "quiet" not in g["line"]
    # 3 long of 5 → mid vs-long (% only); long owns the map.
    assert g["n_long"] == 3
    assert g["long_share_pct"] == 60
    assert g["long_share_severity"] == ""
    assert "vs 3 long · 60%" in g["lean"]
    assert g["vs_long_lead"] == "lead long · 60%"
    assert g["vs_long_lead_name"] == "long"
    assert g["vs_long_lead_pct"] == 60
    assert "lead long · 60%" in g["lean"]
    # 3 long vs 2 short → lead size 1.5×.
    assert g["vs_long_lead_size"] == 1.5
    assert g["vs_long_lead_size_louder"] == 3
    assert g["vs_long_lead_size_quieter"] == 2
    assert "lead size · 1.5×" in g["lean"]
    # Mid short + mid long → both severity silent → lean silent.
    assert g["vs_long_lean"] == ""
    assert g["vs_long_lean_warn"] is False
    assert g["lean_warn"] is False


def test_ledger_short_refuse_vs_long_all_short(tmp_path: Path) -> None:
    """All-short book speaks thin vs 0 long under lean."""
    import json

    (tmp_path / "portfolio.json").write_text(
        json.dumps({"cash": 1000, "holdings": {"TSLA": -1, "ZERO": 0}})
    )
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["short_count"] == 2
    assert g["n_book"] == 2
    assert g["short_share_pct"] == 100
    assert g["short_share_severity"] == "hot"
    assert g["n_long"] == 0
    assert g["long_share_pct"] == 0
    assert g["long_share_severity"] == "thin"
    assert g["lean"].startswith("vs 0 long · thin · 0%")
    assert "short vs long align · hot|thin" in g["lean"]
    assert g["vs_long_lean"] == "short vs long align · hot|thin"
    assert g["vs_long_lean_warn"] is False
    assert g["lean_warn"] is True
    assert "vs 0 long" not in g["line"]
    # Sole-side (all short) stays silent on ownership lead / size.
    assert g["vs_long_lead"] == ""
    assert g["vs_long_sample_gap"] == ""
    assert g["vs_long_lead_size"] is None


def test_ledger_short_refuse_vs_long_tied(tmp_path: Path) -> None:
    """Equal short/long counts speak short/long tied (no strict lead)."""
    import json

    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "cash": 1000,
                "holdings": {
                    "TSLA": -1,
                    "ZERO": 0,
                    "AAPL": 1,
                    "MSFT": 1,
                },
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["short_count"] == 2
    assert g["n_long"] == 2
    assert g["vs_long_lead"] == ""
    assert g["vs_long_sample_gap"] == "short/long tied"
    assert "short/long tied" in g["lean"]
    assert "short/long tied" not in g["line"]
    assert "tied" in g["lean_meta"]
    # Tied → no lead size.
    assert g["vs_long_lead_size"] is None
    assert "lead size" not in g["lean"]
    # 50% short is hot; 50% long is mid → clash · short hot · long ok.
    assert g["short_share_severity"] == "hot"
    assert g["long_share_severity"] == ""
    assert g["vs_long_lean"] == "short vs long clash · short hot · long ok"
    assert g["vs_long_lean_warn"] is True
    assert g["lean_warn"] is True
    assert "clash" in g["lean_meta"]


def test_ledger_short_vs_long_lead_helpers() -> None:
    bit, name, pct = ledger_short_vs_long_lead(2, 3)
    assert bit == "lead long · 60%"
    assert name == "long"
    assert pct == 60
    bit, name, pct = ledger_short_vs_long_lead(3, 2)
    assert bit == "lead short · 60%"
    assert name == "short"
    assert pct == 60
    assert ledger_short_vs_long_lead(2, 2) == ("", "", None)
    assert ledger_short_vs_long_sample_gap(2, 2) == "short/long tied"
    assert ledger_short_vs_long_lead(2, 0) == ("", "", None)
    assert ledger_short_vs_long_sample_gap(2, 0) == ""
    assert ledger_short_vs_long_lead_size(2, 1, lead_name="short") == (
        2.0,
        2,
        1,
    )
    assert ledger_short_vs_long_lead_size(6, 2, lead_name="long") == (
        3.0,
        6,
        2,
    )
    assert ledger_short_vs_long_lead_size(3, 2, lead_name="long") == (
        1.5,
        3,
        2,
    )
    assert ledger_short_vs_long_lead_size(2, 2, lead_name="") == (
        None,
        None,
        None,
    )
    assert ledger_short_vs_long_lead_size(2, 0, lead_name="short") == (
        None,
        None,
        None,
    )


def test_ledger_short_vs_long_lean_helpers() -> None:
    bit, warn = ledger_short_vs_long_lean("hot", "thin")
    assert bit == "short vs long align · hot|thin"
    assert warn is False
    bit, warn = ledger_short_vs_long_lean("quiet", "strong")
    assert bit == "short vs long align · quiet|strong"
    assert warn is False
    bit, warn = ledger_short_vs_long_lean("hot", "strong")
    assert bit == "short vs long clash · short hot · long strong"
    assert warn is True
    bit, warn = ledger_short_vs_long_lean("hot", "")
    assert bit == "short vs long clash · short hot · long ok"
    assert warn is True
    bit, warn = ledger_short_vs_long_lean("quiet", "")
    assert bit == "short vs long clash · short quiet · long ok"
    assert warn is False
    assert ledger_short_vs_long_lean("", "") == ("", False)
    assert ledger_short_vs_long_lean("ok", "ok") == ("", False)


def test_ledger_short_lean_meta() -> None:
    assert ledger_short_lean_meta("") == "quiet"
    quiet = ledger_short_lean_meta(
        "vs 6 long · strong · 75% · lead long · 75% · "
        "lead size · 3× · lead size sides · louder 6 · quieter 2"
        " · short vs long align · quiet|strong"
    )
    assert quiet.startswith("quiet")
    assert "vs long" in quiet
    assert "long" in quiet
    assert "size" in quiet
    assert "sides" in quiet
    assert "align" in quiet
    warn = ledger_short_lean_meta(
        "vs 1 long · thin · 33% · lead short · 67% · "
        "lead size · 2× · lead size sides · louder 2 · quieter 1"
        " · short vs long clash · short hot · long thin",
        warn=True,
    )
    assert warn.startswith("warn")
    assert "vs long" in warn
    assert "short" in warn
    assert "size" in warn
    assert "clash" in warn
