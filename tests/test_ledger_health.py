"""Ledger shard honesty (display only; not a gate)."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.charts import _load_jsonl
from openbb_backend.desk import (
    build_ledger_health,
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
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "bad"
    assert "portfolio malformed" in g["line"]


def test_ledger_missing_portfolio_with_fills_is_thin(tmp_path: Path) -> None:
    (tmp_path / "trades.jsonl").write_text("{}\n")
    g = build_ledger_health(tmp_path)
    assert g["severity"] == "thin"
    assert g["line"] == "ledger thin · no portfolio"
