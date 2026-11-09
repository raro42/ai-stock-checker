"""Ledger shard honesty (display only; not a gate)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.charts import _load_jsonl
from openbb_backend.desk import (
    build_ledger_health,
    ledger_short_lean_meta,
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
    assert g["lean"] == "vs 1 long · thin · 33%"
    assert "vs 1 long" not in g["line"]
    assert "vs 1 long" in g["bit"]
    assert g["lean_warn"] is True
    assert "vs long" in g["lean_meta"]


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
    # 6 long of 8 → strong; lean closed (not warn).
    assert g["n_long"] == 6
    assert g["long_share_pct"] == 75
    assert g["long_share_severity"] == "strong"
    assert g["lean"] == "vs 6 long · strong · 75%"
    assert "vs 6 long" not in g["line"]
    assert g["lean_warn"] is False
    assert g["lean_meta"].startswith("quiet")


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
    # 3 long of 5 → mid vs-long (% only).
    assert g["n_long"] == 3
    assert g["long_share_pct"] == 60
    assert g["long_share_severity"] == ""
    assert g["lean"] == "vs 3 long · 60%"
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
    assert g["lean"] == "vs 0 long · thin · 0%"
    assert g["lean_warn"] is True
    assert "vs 0 long" not in g["line"]


def test_ledger_short_lean_meta() -> None:
    assert ledger_short_lean_meta("") == "quiet"
    quiet = ledger_short_lean_meta("vs 6 long · strong · 75%")
    assert quiet.startswith("quiet")
    assert "vs long" in quiet
    warn = ledger_short_lean_meta("vs 1 long · thin · 33%", warn=True)
    assert warn.startswith("warn")
    assert "vs long" in warn
