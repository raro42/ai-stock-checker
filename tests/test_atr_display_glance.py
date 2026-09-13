"""Screener ATR display-only honesty glance (not live stops)."""

from __future__ import annotations

import json

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_atr_display_glance, load_desk_snapshot
from stock_checker.atr_risk import DEFAULT_ATR_MULT
from stock_checker.exit_policy import DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT


def test_atr_display_glance_ready() -> None:
    g = build_atr_display_glance()
    assert g["ready"] is True
    assert g["tone"] == "display"
    assert g["live_atr_stops"] is False
    assert g["vol_total"] == 0
    assert g["vol_missing"] == 0
    assert g["atr_mult"] == float(DEFAULT_ATR_MULT)
    assert g["take_profit_pct"] == float(DEFAULT_TAKE_PROFIT_PCT)
    assert g["stop_loss_pct"] == float(DEFAULT_STOP_LOSS_PCT)
    assert "display only" in g["line"]
    assert "not ATR" in g["line"]
    assert f"~{DEFAULT_ATR_MULT:g}×" in g["line"]
    assert f"+{DEFAULT_TAKE_PROFIT_PCT:g}%" in g["line"]
    assert f"−{DEFAULT_STOP_LOSS_PCT:g}%" in g["line"]


def test_atr_display_glance_vol_coverage() -> None:
    g = build_atr_display_glance(
        [
            {"risk_note": "stop atr €100 (−5%) · tgt +20% · R:R 4.0 (ok)"},
            {"risk_note": "risk n/a"},
            {"risk_note": "stop swing €90 (−4%) · tgt +20%"},
        ]
    )
    assert g["vol_total"] == 3
    assert g["vol_with"] == 2
    assert g["vol_missing"] == 1
    assert g["tone"] == "warn"
    assert "2/3 with vol" in g["line"]
    assert "1 soft n/a" in g["line"]
    assert "not ATR" in g["line"]
    assert g["live_atr_stops"] is False

    all_ok = build_atr_display_glance(
        [{"risk_note": "stop atr €10 (−4%) · tgt +20%"}]
    )
    assert all_ok["tone"] == "display"
    assert all_ok["vol_missing"] == 0
    assert "1/1 with vol" in all_ok["line"]
    assert "soft n/a" not in all_ok["line"]


def test_atr_display_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    arch = tmp_path / "archive"
    arch.mkdir()
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "crypto_leaders": [
                    {"symbol": "BTC-USD", "risk_note": "risk n/a"},
                ],
                "stock_breakouts": [
                    {
                        "symbol": "AAPL",
                        "risk_note": "stop atr €100 (−5%) · tgt +20%",
                    },
                ],
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["atr_display_glance"]
    assert g["ready"] is True
    assert g["live_atr_stops"] is False
    assert g["vol_total"] == 2
    assert g["vol_with"] == 1
    assert g["vol_missing"] == 1
    assert "1/2 with vol" in g["line"]


def test_atr_display_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["atr_display_glance"]
    assert g["ready"] is True
    assert g["live_atr_stops"] is False
    assert "not ATR" in g["line"]
