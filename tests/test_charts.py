#!/usr/bin/env python3
"""Offline tests for desk chart series."""

import json
from pathlib import Path

from openbb_backend.charts import build_equity_curve, load_chart_payload


def _seed(data: Path) -> None:
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 80000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 1,
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-20 10:00:00",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
                "cash_remaining": 89999,
            }
        )
        + "\n"
    )
    (data / "archive").mkdir(parents=True, exist_ok=True)
    (data / "archive" / "opportunities_latest.json").write_text("{}")


def test_equity_curve_from_fills(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_equity_curve(tmp_path)
    assert len(pts) >= 2
    assert pts[0]["equity"] == 100000
    assert pts[1]["label"].startswith("BUY")


def test_chart_payload_offline(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    assert "equity" in payload and "allocation" in payload
    assert "from_buy" in payload
    assert "breadth_glance" in payload
    assert payload["breadth_glance"]["ready"] is False
    assert "scan_freshness" in payload
    assert payload["scan_freshness"]["ready"] is False
    assert "soft_allow_glance" in payload
    assert payload["soft_allow_glance"]["ready"] is False
    assert "book_risk_glance" in payload
    assert payload["book_risk_glance"]["ready"] is True
    assert payload["book_risk_glance"]["posture"] == "open"
    assert "1/5" in payload["book_risk_glance"]["slots"]
    assert "mark_coverage" in payload
    assert payload["mark_coverage"]["ready"] is True
    assert payload["mark_coverage"]["severity"] == "none"
    assert payload["mark_coverage"]["line"] == "price coverage none · 0/1"
    assert "price_bars_glance" in payload
    assert payload["price_bars_glance"]["ready"] is False
    assert payload["ledger_health"]["ready"] is True
    assert payload["ledger_health"]["severity"] == "ok"
    assert payload["ledger_health"]["line"] == "ledger ok"
    assert "pretrade_glance" in payload
    assert payload["pretrade_glance"]["ready"] is True
    assert payload["pretrade_glance"]["level"] == "PASS"
    assert "next_buy_glance" in payload
    assert payload["next_buy_glance"]["ready"] is True
    assert payload["next_buy_glance"]["tone"] == "open"
    assert "Next buy" in payload["next_buy_glance"]["line"]
    assert "entry_gates_glance" in payload
    assert payload["entry_gates_glance"]["ready"] is True
    assert payload["entry_gates_glance"]["tone"] == "strict"
    assert "regime on" in payload["entry_gates_glance"]["line"]
    assert "calm_streak_glance" in payload
    assert payload["calm_streak_glance"]["ready"] is True
    assert "0/30" in payload["calm_streak_glance"]["line"]
    assert "promote_ab_glance" in payload
    assert payload["promote_ab_glance"]["ready"] is True
    assert "Window" in payload["promote_ab_glance"]["line"]
    assert "fee_burn_glance" in payload
    assert payload["fee_burn_glance"]["ready"] is True
    assert payload["fee_burn_glance"]["tone"] == "quiet"
    assert payload["fee_burn_glance"]["realized"] is None
    assert "€1.00 fees" in payload["fee_burn_glance"]["line"]
    assert "P&L" not in payload["fee_burn_glance"]["line"]
    assert "postmortem_glance" in payload
    assert payload["postmortem_glance"]["ready"] is False
    assert any(a["symbol"] == "CASH" for a in payload["allocation"])
    assert any(a["symbol"] == "AAPL" for a in payload["allocation"])
    # Charts used to omit the chip and fall back to the static category index.
    assert payload["policy_honesty_warn"] is True
    assert payload["policy_honesty_meta"].startswith("warn · ")
    assert "Yahoo stale" in payload["policy_honesty_meta"]
    assert "quiet ·" in payload["policy_honesty_meta"]
    assert payload["policy_honesty_meta"] != "crypto · exits · AI · gates · fees"


def test_chart_payload_entry_gates_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "regime_gate": True,
                "rs_gate": False,
                "breadth_gate": True,
                "promote_experiment_strategy": True,
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["entry_gates_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "mixed"
    assert glance["regime"] is True
    assert glance["rs"] is False
    assert glance["breadth"] is True
    assert glance["promote"] is True
    assert "RS off" in glance["line"]


def test_chart_payload_calm_streak_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "paper_calm.json").write_text(
        json.dumps(
            {
                "streak_days": 12,
                "required_days": 30,
                "ready_for_compose_default": False,
                "detail": "fee quiet",
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["calm_streak_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "progress"
    assert glance["streak"] == 12
    assert glance["required"] == 30
    assert "12/30" in glance["line"]
    assert "building" in glance["line"]
    assert "fee quiet" in glance["line"]



def test_chart_payload_promote_ab_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"promote_experiment_strategy": True})
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["promote_ab_glance"]
    assert glance["ready"] is True
    assert glance["promote_on"] is True
    assert glance["protocol_ok"] is False
    assert glance["tone"] == "warn"
    assert "Window A" in glance["line"]
    assert "promote on" in glance["line"]


def test_chart_payload_fee_burn_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 8000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 250,
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["fee_burn_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert glance["high"] is True
    assert "2.5%" in glance["line"]
    assert "high" in glance["line"]


def test_chart_payload_stuck_capital_glance(tmp_path: Path, monkeypatch):
    import time

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    now = 1_700_000_000.0
    monkeypatch.setattr(time, "time", lambda: now)
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 5000,
                "holdings": {"EXPE": 10},
                "avg_buy_price": {"EXPE": 100},
                "total_fees_paid": 0,
            }
        )
    )
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"EXPE": now - 48 * 3600})
    )
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"min_hold_hours": 24})
    )
    arch = tmp_path / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "stock_breakouts": [
                    {"symbol": "EXPE", "price": 92.0, "pct_from_high": 0.05}
                ]
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["stuck_capital_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert glance["count"] == 1
    assert "EXPE" in glance["line"]
    assert "past min-hold underwater" in glance["line"]


def test_chart_payload_min_hold_lock_glance(tmp_path: Path, monkeypatch):
    import time

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    now = 1_700_000_000.0
    monkeypatch.setattr(time, "time", lambda: now)
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 5000,
                "holdings": {"AAPL": 5, "MSFT": 3},
                "avg_buy_price": {"AAPL": 100, "MSFT": 200},
                "total_fees_paid": 0,
            }
        )
    )
    (tmp_path / "entry_times.json").write_text(
        json.dumps(
            {
                "AAPL": now - 3600,
                "MSFT": now - 100_000,
            }
        )
    )
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"min_hold_hours": 24})
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["min_hold_lock_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "flat"
    assert glance["locked"] == 1
    assert glance["timed"] == 2
    assert glance["earliest_symbol"] == "AAPL"
    assert "1/2 in min-hold lock" in glance["line"]


def test_chart_payload_next_buy_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["next_buy_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "open"
    assert glance["eur"] > 0
    assert glance["slots_open"] == 4
    assert "Next buy" in glance["line"]


def test_chart_payload_postmortem_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-07-20 10:00:00",
                        "type": "BUY",
                        "symbol": "AAPL",
                        "quantity": 10,
                        "price": 100,
                        "commission": 1,
                        "note": "momentum",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-07-21 12:00:00",
                        "type": "SELL",
                        "symbol": "AAPL",
                        "quantity": 10,
                        "price": 108,
                        "commission": 1,
                        "exit_reason": "take_profit",
                        "profit_loss": 80,
                    }
                ),
            ]
        )
        + "\n"
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["postmortem_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "up"
    assert glance["symbol"] == "AAPL"
    assert "Last exit · AAPL" in glance["line"]
    assert "take_profit" in glance["line"]
    assert "+8.0%" in glance["line"]


def test_chart_payload_book_risk_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["book_risk_glance"]
    assert glance["ready"] is True
    assert glance["posture"] == "open"
    assert glance["slots"] == "1/5"
    assert "1/5" in glance["line"]


def test_chart_payload_pretrade_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["pretrade_glance"]
    assert glance["ready"] is True
    assert glance["level"] == "PASS"
    assert glance["tone"] == "pass"


def test_chart_payload_soft_allow_glance(tmp_path: Path, monkeypatch):
    from stock_checker.gate_audit import record_soft_allow

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    record_soft_allow(tmp_path, "rs", "insufficient history")
    payload = load_chart_payload(tmp_path)
    glance = payload["soft_allow_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert "[rs]" in glance["line"]
    assert "insufficient history" in glance["line"]


def test_chart_payload_scan_freshness_from_archive(tmp_path: Path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    scan_when = datetime.now(timezone.utc) - timedelta(minutes=5)
    stamp = scan_when.strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "archive" / "opportunities_latest.json").write_text(
        json.dumps({"scan_time": stamp})
    )
    payload = load_chart_payload(tmp_path)
    fresh = payload["scan_freshness"]
    assert fresh["ready"] is True
    assert fresh["tone"] == "fresh"
    assert fresh["scan_time"] == stamp


def test_chart_payload_breadth_glance_from_daily(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "scan_breadth_daily.json").write_text(
        json.dumps(
            [
                {
                    "day": "2026-09-07",
                    "crypto_n": 4,
                    "crypto_up": 3,
                    "crypto_down": 1,
                    "crypto_big_movers": 1,
                    "stock_scan_n": 10,
                    "stock_scan_up": 6,
                    "stock_scan_down": 4,
                    "stock_within_5pct_high": 2,
                    "stock_breakouts_n": 3,
                }
            ]
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["breadth_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "up"
    assert "crypto 3/1" in glance["line"]
    assert "stock 6/4" in glance["line"]
    assert "estimate · not full-universe" in glance["line"]
    assert glance["estimate"] is True
    assert glance["full_universe"] is False


def test_chart_last_bar_meta_fresh_aging_stale():
    """tradermonty #675 display-only: last daily close age band."""
    from datetime import datetime, timezone

    from openbb_backend.charts import chart_last_bar_meta

    now = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
    fresh = chart_last_bar_meta(
        [{"t": "2026-11-08T10:00:00Z", "close": 100}], now=now
    )
    assert fresh["bar_freshness"] == "fresh"
    assert fresh["last_bar"] == "2026-11-08"
    assert fresh["bar_age_label"]

    aging = chart_last_bar_meta(
        [{"t": "2026-11-07T10:00:00Z", "close": 100}], now=now
    )
    assert aging["bar_freshness"] == "aging"

    stale = chart_last_bar_meta(
        [{"t": "2026-11-01T00:00:00Z", "close": 100}], now=now
    )
    assert stale["bar_freshness"] == "stale"
    assert stale["last_bar"] == "2026-11-01"
    assert chart_last_bar_meta([])["bar_freshness"] == ""
    assert chart_last_bar_meta([{"t": "nope", "close": 1}])["bar_freshness"] == ""


def test_chart_price_bars_glance_share_after_spoken():
    """Book-level aging|stale ownership after per-legend bits (display only)."""
    from openbb_backend.charts import (
        chart_price_bars_aging_stale_delta,
        chart_price_bars_aging_stale_delta_lead,
        chart_price_bars_aging_stale_delta_lead_size,
        chart_price_bars_aging_stale_lead,
        chart_price_bars_aging_stale_lead_size,
        chart_price_bars_aging_stale_lean,
        chart_price_bars_aging_stale_sample_gap,
        chart_price_bars_aging_stale_share_bands,
        chart_price_bars_glance,
        chart_price_bars_lean_meta,
        chart_price_bars_spoken_vs_fresh_delta,
        chart_price_bars_spoken_vs_fresh_delta_lead,
        chart_price_bars_spoken_vs_fresh_delta_lead_size,
        chart_price_bars_spoken_vs_fresh_lead,
        chart_price_bars_spoken_vs_fresh_lead_size,
        chart_price_bars_spoken_vs_fresh_lean,
        chart_price_bars_spoken_vs_fresh_sample_gap,
        chart_price_bars_vs_fresh,
    )

    assert chart_price_bars_glance([])["ready"] is False
    assert chart_price_bars_glance(
        [{"bar_freshness": "fresh"}, {"bar_freshness": "fresh"}]
    )["ready"] is False

    hot = chart_price_bars_glance(
        [
            {"bar_freshness": "stale"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "fresh"},
        ]
    )
    assert hot["ready"] is True
    assert hot["n_stale"] == 2
    assert hot["n_spoken"] == 2
    assert hot["spoken_share_pct"] == 66.7
    assert hot["spoken_share_severity"] == "hot"
    assert hot["tone"] == "warn"
    assert hot["bit_core"] == "2 bars stale · hot · 66.7%"
    assert hot["line"] == hot["bit_core"]
    assert "2 bars stale" in hot["bit"]
    assert "hot · 66.7%" in hot["bit"]
    assert hot["vs_fresh"] == "vs 1 fresh · thin · 33.3%"
    assert hot["vs_fresh_severity"] == "thin"
    assert "vs 1 fresh · thin · 33.3%" in hot["bit"]
    assert "vs 1 fresh · thin · 33.3%" in hot["lean"]
    assert hot["spoken_vs_fresh_lead"] == "lead spoken · 67%"
    assert hot["spoken_vs_fresh_lead_name"] == "spoken"
    assert "lead spoken · 67%" in hot["bit"]
    assert hot["bit"].index("vs 1 fresh") < hot["bit"].index("lead spoken")
    assert hot["spoken_vs_fresh_lead_size"] == 2.0
    assert hot["spoken_vs_fresh_lead_size_louder"] == 2
    assert hot["spoken_vs_fresh_lead_size_quieter"] == 1
    assert "sf size · 2×" in hot["bit"]
    assert "sf size sides · spoken 2 · fresh 1" in hot["bit"]
    assert "louder" not in hot["bit"]
    assert "quieter" not in hot["bit"]
    assert hot["spoken_vs_fresh_lean"] == "spoken vs fresh align · hot|thin"
    assert hot["spoken_vs_fresh_lean_warn"] is False
    assert "spoken vs fresh align · hot|thin" in hot["bit"]
    assert "spoken vs fresh align · hot|thin" in hot["lean"]
    assert hot["bit"].index("sf size") < hot["bit"].index(
        "spoken vs fresh align"
    )
    # spoken 66.7 − fresh 33.3 → +33pp wide; adverse hot|thin + wide warns
    assert hot["spoken_vs_fresh_delta_pp"] == 33
    assert hot["spoken_vs_fresh_delta_severity"] == "wide"
    assert hot["spoken_vs_fresh_lean_vs_delta"] == "align · wide"
    assert hot["spoken_vs_fresh_lean_vs_delta_warn"] is True
    assert "Δ wide · +33pp" in hot["bit"]
    assert "lean vs Δ align · wide" in hot["bit"]
    assert hot["bit"].index("spoken vs fresh align") < hot["bit"].index(
        "Δ wide"
    )
    assert hot["spoken_vs_fresh_delta_lead"] == "spoken"
    assert "Δ lead · spoken" in hot["bit"]
    assert "Δ lead · spoken" in hot["lean"]
    assert hot["bit"].index("lean vs Δ") < hot["bit"].index("Δ lead · spoken")
    # louder 66.7% ÷ quieter 33.3% → ~2×; named spoken|fresh sides
    assert hot["spoken_vs_fresh_delta_lead_size"] == 2.0
    assert hot["spoken_vs_fresh_delta_lead_size_louder"] == 66.7
    assert hot["spoken_vs_fresh_delta_lead_size_quieter"] == 33.3
    assert "Δ lead size · 2×" in hot["bit"]
    assert "Δ lead size sides · spoken 66.7% · fresh 33.3%" in hot["bit"]
    assert hot["bit"].index("Δ lead · spoken") < hot["bit"].index(
        "Δ lead size · 2×"
    )
    assert hot["aging_stale_lead"] == ""  # sole-side silent
    assert hot["aging_stale_lead_size"] is None
    assert hot["aging_stale_lean"] == ""  # sole-side silent
    assert hot["aging_share_pct"] is None
    assert hot["aging_stale_delta_pp"] is None  # lean silent → no as Δ
    assert hot["aging_stale_delta_severity"] == ""
    assert hot["aging_stale_delta_lead"] == ""
    assert hot["lean_warn"] is True
    assert hot["lean_meta"].startswith("warn ·")
    assert "vs fresh" in hot["lean_meta"]
    assert "spoken" in hot["lean_meta"]
    assert "sf size" in hot["lean_meta"] or "sf sides" in hot["lean_meta"]

    mixed = chart_price_bars_glance(
        [
            {"bar_freshness": "aging"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "fresh"},
            {"bar_freshness": "fresh"},
        ]
    )
    assert mixed["bit"].startswith("1 aging · 1 stale")
    assert mixed["bit_core"].startswith("1 aging · 1 stale")
    assert mixed["spoken_share_pct"] == 50.0
    assert mixed["spoken_share_severity"] == "hot"
    assert mixed["vs_fresh"] == "vs 2 fresh · 50%"
    assert mixed["vs_fresh_severity"] == ""  # mid
    assert mixed["spoken_vs_fresh_sample_gap"] == "spoken/fresh tied"
    assert "spoken/fresh tied" in mixed["bit"]
    assert "spoken/fresh tied" in mixed["lean"]
    assert mixed["spoken_vs_fresh_lead_size"] is None  # tied → no sf size
    # spoken hot + mid fresh → clash (sole lean)
    assert mixed["spoken_vs_fresh_lean"] == (
        "spoken vs fresh clash · spoken hot · fresh ok"
    )
    assert mixed["spoken_vs_fresh_lean_warn"] is True
    assert "spoken vs fresh clash · spoken hot · fresh ok" in mixed["lean"]
    # spoken 50 − fresh 50 → 0pp thin; lean vs Δ align · thin (no adverse warn)
    assert mixed["spoken_vs_fresh_delta_pp"] == 0
    assert mixed["spoken_vs_fresh_delta_severity"] == "thin"
    assert mixed["spoken_vs_fresh_lean_vs_delta"] == "align · thin"
    assert mixed["spoken_vs_fresh_lean_vs_delta_warn"] is False
    assert "Δ thin · 0pp" in mixed["bit"]
    assert "lean vs Δ align · thin" in mixed["bit"]
    assert mixed["spoken_vs_fresh_delta_lead"] == ""  # 0pp silent
    assert "Δ lead ·" not in mixed["bit"]
    assert mixed["spoken_vs_fresh_delta_lead_size"] is None
    assert "Δ lead size" not in mixed["bit"]
    assert mixed["aging_stale_sample_gap"] == "aging/stale tied"
    assert "aging/stale tied" in mixed["bit"]
    assert mixed["bit"].index("spoken/fresh tied") < mixed["bit"].index(
        "aging/stale tied"
    )
    assert mixed["aging_stale_lead_size"] is None  # tied → no size
    # 50/50 → both hot → clash (postmortem skip-reason parity)
    assert mixed["aging_share_pct"] == 50
    assert mixed["stale_share_pct"] == 50
    assert mixed["aging_share_severity"] == "hot"
    assert mixed["stale_share_severity"] == "hot"
    assert mixed["aging_stale_lean"] == (
        "aging vs stale clash · aging hot · stale hot"
    )
    assert mixed["aging_stale_lean_warn"] is True
    assert "aging vs stale clash · aging hot · stale hot" in mixed["lean"]
    assert mixed["bit"].index("aging/stale tied") < mixed["bit"].index(
        "aging vs stale clash"
    )
    # aging 50 − stale 50 → 0pp thin; as Δ distinct from spoken/fresh Δ
    assert mixed["aging_stale_delta_pp"] == 0
    assert mixed["aging_stale_delta_severity"] == "thin"
    assert mixed["aging_stale_lean_vs_delta"] == "align · thin"
    assert mixed["aging_stale_lean_vs_delta_warn"] is False
    assert "as Δ thin · 0pp" in mixed["bit"]
    assert "as lean vs Δ align · thin" in mixed["bit"]
    assert mixed["bit"].index("aging vs stale clash") < mixed["bit"].index(
        "as Δ thin"
    )
    assert mixed["aging_stale_delta_lead"] == ""  # 0pp silent
    assert "as Δ lead ·" not in mixed["bit"]
    assert mixed["lean_warn"] is True
    assert "sf tied" in mixed["lean_meta"]
    # Cap 4 stages → aging/stale tied / as lean / as Δ may clip as +N.
    assert (
        "as tied" in mixed["lean_meta"]
        or "as lean" in mixed["lean_meta"]
        or "as Δ" in mixed["lean_meta"]
        or "+1" in mixed["lean_meta"]
        or "Δ" in mixed["lean_meta"]
    )

    lead = chart_price_bars_glance(
        [
            {"bar_freshness": "aging"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "fresh"},
        ]
    )
    assert lead["aging_stale_lead"] == "lead stale · 67%"
    assert lead["aging_stale_lead_name"] == "stale"
    assert lead["aging_stale_lead_share_pct"] == 67
    assert "lead stale · 67%" in lead["bit"]
    assert "lead stale · 67%" in lead["lean"]
    assert lead["vs_fresh"] == "vs 1 fresh · thin · 25%"
    assert lead["spoken_vs_fresh_lead"] == "lead spoken · 75%"
    assert "lead spoken · 75%" in lead["bit"]
    assert lead["spoken_vs_fresh_lead_size"] == 3.0
    assert lead["spoken_vs_fresh_lead_size_louder"] == 3
    assert lead["spoken_vs_fresh_lead_size_quieter"] == 1
    assert "sf size · 3×" in lead["bit"]
    assert "sf size sides · spoken 3 · fresh 1" in lead["bit"]
    assert lead["bit"].index("lead spoken") < lead["bit"].index("sf size")
    assert lead["spoken_vs_fresh_lean"] == "spoken vs fresh align · hot|thin"
    assert "spoken vs fresh align · hot|thin" in lead["bit"]
    assert lead["bit"].index("sf size") < lead["bit"].index(
        "spoken vs fresh align"
    )
    # spoken 75 − fresh 25 → +50pp wide; adverse hot|thin + wide warns
    assert lead["spoken_vs_fresh_delta_pp"] == 50
    assert lead["spoken_vs_fresh_delta_severity"] == "wide"
    assert lead["spoken_vs_fresh_lean_vs_delta"] == "align · wide"
    assert lead["spoken_vs_fresh_lean_vs_delta_warn"] is True
    assert "Δ wide · +50pp" in lead["bit"]
    assert "lean vs Δ align · wide" in lead["bit"]
    assert lead["bit"].index("spoken vs fresh align") < lead["bit"].index(
        "Δ wide"
    )
    assert lead["spoken_vs_fresh_delta_lead"] == "spoken"
    assert "Δ lead · spoken" in lead["bit"]
    assert lead["bit"].index("lean vs Δ") < lead["bit"].index("Δ lead · spoken")
    # louder 75% ÷ quieter 25% → 3×; named spoken|fresh sides
    assert lead["spoken_vs_fresh_delta_lead_size"] == 3.0
    assert lead["spoken_vs_fresh_delta_lead_size_louder"] == 75.0
    assert lead["spoken_vs_fresh_delta_lead_size_quieter"] == 25.0
    assert "Δ lead size · 3×" in lead["bit"]
    assert "Δ lead size sides · spoken 75% · fresh 25%" in lead["bit"]
    assert lead["bit"].index("Δ lead · spoken") < lead["bit"].index(
        "Δ lead size · 3×"
    )
    assert lead["bit"].index("Δ lead size · 3×") < lead["bit"].index(
        "lead stale"
    )
    assert lead["aging_stale_sample_gap"] == ""
    assert lead["aging_stale_lead_size"] == 2.0
    assert lead["aging_stale_lead_size_louder"] == 2
    assert lead["aging_stale_lead_size_quieter"] == 1
    assert "lead size · 2×" in lead["bit"]
    assert "lead size sides · stale 2 · aging 1" in lead["bit"]
    assert "louder" not in lead["bit"]
    assert "quieter" not in lead["bit"]
    assert "lead size · 2×" in lead["lean"]
    assert "lead size sides · stale 2 · aging 1" in lead["lean"]
    # aging 33 mid · stale 67 hot → sole hot clash warns
    assert lead["aging_share_pct"] == 33
    assert lead["stale_share_pct"] == 67
    assert lead["aging_share_severity"] == ""
    assert lead["stale_share_severity"] == "hot"
    assert lead["aging_stale_lean"] == (
        "aging vs stale clash · aging ok · stale hot"
    )
    assert lead["aging_stale_lean_warn"] is True
    assert "aging vs stale clash · aging ok · stale hot" in lead["lean"]
    assert lead["bit"].index("lead size sides") < lead["bit"].index(
        "aging vs stale clash"
    )
    # aging 33 − stale 67 → −34pp wide; complementary calm → no asΔ warn
    assert lead["aging_stale_delta_pp"] == -34
    assert lead["aging_stale_delta_severity"] == "wide"
    assert lead["aging_stale_lean_vs_delta"] == "align · wide"
    assert lead["aging_stale_lean_vs_delta_warn"] is False
    assert "as Δ wide · -34pp" in lead["bit"]
    assert "as lean vs Δ align · wide" in lead["bit"]
    assert lead["bit"].index("aging vs stale clash") < lead["bit"].index(
        "as Δ wide"
    )
    # aging% − stale% negative → stale owns as Δ; distinct from spoken Δ lead
    assert lead["aging_stale_delta_lead"] == "stale"
    assert "as Δ lead · stale" in lead["bit"]
    assert "as Δ lead · stale" in lead["lean"]
    assert lead["bit"].index("as lean vs Δ") < lead["bit"].index(
        "as Δ lead · stale"
    )
    # quieter aging% > 0 → as Δ lead size + named sides (≠ spoken Δ lead size)
    assert lead["aging_stale_delta_lead_size"] == round(67 / 33, 2)
    assert lead["aging_stale_delta_lead_size_louder"] == 67
    assert lead["aging_stale_delta_lead_size_quieter"] == 33
    assert "as Δ lead size · 2.03×" in lead["bit"]
    assert "as Δ lead size sides · stale 67% · aging 33%" in lead["bit"]
    assert "quieter" not in lead["bit"]
    assert lead["bit"].index("as Δ lead · stale") < lead["bit"].index(
        "as Δ lead size ·"
    )
    assert lead["lean_meta"].startswith("warn ·")
    # Cap 4 stages → later as Δ size / sides clipped as +N.
    assert (
        "+1" in lead["lean_meta"]
        or "sf size" in lead["lean_meta"]
        or "as lean" in lead["lean_meta"]
        or "as Δ size" in lead["lean_meta"]
        or "as Δ lead" in lead["lean_meta"]
        or "as Δ" in lead["lean_meta"]
    )

    # Complementary hot|quiet after lead size (3 stale · 1 aging)
    as_align = chart_price_bars_glance(
        [
            {"bar_freshness": "aging"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "stale"},
            {"bar_freshness": "stale"},
        ]
    )
    assert as_align["aging_share_pct"] == 25
    assert as_align["stale_share_pct"] == 75
    assert as_align["aging_share_severity"] == "quiet"
    assert as_align["stale_share_severity"] == "hot"
    assert as_align["aging_stale_lean"] == "aging vs stale align · quiet|hot"
    assert as_align["aging_stale_lean_warn"] is False
    assert "aging vs stale align · quiet|hot" in as_align["lean"]
    assert as_align["bit"].index("lead size") < as_align["bit"].index(
        "aging vs stale align"
    )
    # aging 25 − stale 75 → −50pp wide; quiet|hot stays calm (no asΔ warn)
    assert as_align["aging_stale_delta_pp"] == -50
    assert as_align["aging_stale_delta_severity"] == "wide"
    assert as_align["aging_stale_lean_vs_delta"] == "align · wide"
    assert as_align["aging_stale_lean_vs_delta_warn"] is False
    assert "as Δ wide · -50pp" in as_align["bit"]
    assert "as lean vs Δ align · wide" in as_align["bit"]
    assert as_align["bit"].index("aging vs stale align") < as_align["bit"].index(
        "as Δ wide"
    )
    assert as_align["aging_stale_delta_lead"] == "stale"
    assert "as Δ lead · stale" in as_align["bit"]
    assert as_align["bit"].index("as lean vs Δ") < as_align["bit"].index(
        "as Δ lead · stale"
    )
    assert as_align["aging_stale_delta_lead_size"] == 3.0
    assert as_align["aging_stale_delta_lead_size_louder"] == 75.0
    assert as_align["aging_stale_delta_lead_size_quieter"] == 25.0
    assert "as Δ lead size · 3×" in as_align["bit"]
    assert "as Δ lead size sides · stale 75% · aging 25%" in as_align["bit"]
    assert as_align["bit"].index("as Δ lead · stale") < as_align["bit"].index(
        "as Δ lead size ·"
    )

    all_spoken = chart_price_bars_glance(
        [
            {"bar_freshness": "stale"},
            {"bar_freshness": "aging"},
        ]
    )
    assert all_spoken["vs_fresh"] == "vs 0 fresh · thin · 0%"
    assert all_spoken["spoken_vs_fresh_lead"] == ""  # sole-side silent
    assert all_spoken["spoken_vs_fresh_sample_gap"] == ""
    assert all_spoken["spoken_vs_fresh_lead_size"] is None

    assert chart_price_bars_aging_stale_lead(2, 1)[0] == "lead aging · 67%"
    assert chart_price_bars_aging_stale_sample_gap(1, 1) == "aging/stale tied"
    assert chart_price_bars_aging_stale_lead(3, 0)[0] == ""
    assert chart_price_bars_aging_stale_share_bands(1, 3) == (
        25,
        "quiet",
        75,
        "hot",
    )
    assert chart_price_bars_aging_stale_share_bands(1, 1) == (
        50,
        "hot",
        50,
        "hot",
    )
    assert chart_price_bars_aging_stale_share_bands(3, 0) == (
        None,
        "",
        None,
        "",
    )
    assert chart_price_bars_aging_stale_lean("quiet", "hot") == (
        "aging vs stale align · quiet|hot",
        False,
    )
    assert chart_price_bars_aging_stale_lean("hot", "quiet") == (
        "aging vs stale align · hot|quiet",
        False,
    )
    assert chart_price_bars_aging_stale_lean("hot", "hot") == (
        "aging vs stale clash · aging hot · stale hot",
        True,
    )
    assert chart_price_bars_aging_stale_lean("", "hot") == (
        "aging vs stale clash · aging ok · stale hot",
        True,
    )
    assert chart_price_bars_aging_stale_lean("", "") == ("", False)
    assert chart_price_bars_aging_stale_delta(
        25, 75, lean_bit="aging vs stale align · quiet|hot"
    ) == (-50, "wide", "align · wide", False)
    assert chart_price_bars_aging_stale_delta(
        50, 50, lean_bit="aging vs stale clash · aging hot · stale hot"
    ) == (0, "thin", "align · thin", False)
    assert chart_price_bars_aging_stale_delta(
        42, 58, lean_bit="aging vs stale clash · aging ok · stale hot"
    ) == (-16, "", "clash · lean · Δ mid", True)
    assert chart_price_bars_aging_stale_delta(25, 75, lean_bit="") == (
        None,
        "",
        "",
        False,
    )
    assert (
        chart_price_bars_aging_stale_delta_lead(
            -34, "wide", lean_vs_delta="align · wide"
        )
        == "stale"
    )
    assert (
        chart_price_bars_aging_stale_delta_lead(
            50, "wide", lean_vs_delta="align · wide"
        )
        == "aging"
    )
    assert (
        chart_price_bars_aging_stale_delta_lead(
            0, "thin", lean_vs_delta="align · thin"
        )
        == ""
    )
    assert (
        chart_price_bars_aging_stale_delta_lead(
            -16, "", lean_vs_delta="clash · lean · Δ mid"
        )
        == ""
    )
    assert (
        chart_price_bars_aging_stale_delta_lead(
            -34, "wide", lean_vs_delta=""
        )
        == ""
    )
    assert chart_price_bars_aging_stale_delta_lead_size(
        33, 67, delta_lead="stale"
    ) == (round(67 / 33, 2), 67.0, 33.0)
    assert chart_price_bars_aging_stale_delta_lead_size(
        25.0, 75.0, delta_lead="stale"
    ) == (3.0, 75.0, 25.0)
    assert chart_price_bars_aging_stale_delta_lead_size(
        75.0, 25.0, delta_lead="aging"
    ) == (3.0, 75.0, 25.0)
    assert chart_price_bars_aging_stale_delta_lead_size(
        75.0, 25.0, delta_lead=""
    ) == (None, None, None)
    assert chart_price_bars_aging_stale_delta_lead_size(
        100.0, 0.0, delta_lead="aging"
    ) == (None, None, None)
    assert chart_price_bars_aging_stale_lead_size(2, 1, lead_name="aging") == (
        2.0,
        2,
        1,
    )
    assert chart_price_bars_aging_stale_lead_size(3, 1, lead_name="aging") == (
        3.0,
        3,
        1,
    )
    assert chart_price_bars_aging_stale_lead_size(1, 1, lead_name="") == (
        None,
        None,
        None,
    )
    assert chart_price_bars_aging_stale_lead_size(2, 0, lead_name="aging") == (
        None,
        None,
        None,
    )
    assert chart_price_bars_spoken_vs_fresh_lead_size(
        2, 1, lead_name="spoken"
    ) == (2.0, 2, 1)
    assert chart_price_bars_spoken_vs_fresh_lead_size(
        1, 3, lead_name="fresh"
    ) == (3.0, 3, 1)
    assert chart_price_bars_spoken_vs_fresh_lead_size(
        1, 1, lead_name=""
    ) == (None, None, None)
    assert chart_price_bars_spoken_vs_fresh_lead_size(
        2, 0, lead_name="spoken"
    ) == (None, None, None)
    assert chart_price_bars_spoken_vs_fresh_lean("hot", "thin") == (
        "spoken vs fresh align · hot|thin",
        False,
    )
    assert chart_price_bars_spoken_vs_fresh_lean("quiet", "strong") == (
        "spoken vs fresh align · quiet|strong",
        False,
    )
    assert chart_price_bars_spoken_vs_fresh_lean("hot", "strong") == (
        "spoken vs fresh clash · spoken hot · fresh strong",
        True,
    )
    assert chart_price_bars_spoken_vs_fresh_lean("hot", "") == (
        "spoken vs fresh clash · spoken hot · fresh ok",
        True,
    )
    assert chart_price_bars_spoken_vs_fresh_lean("", "") == ("", False)
    assert chart_price_bars_spoken_vs_fresh_delta(
        66.7,
        33.3,
        lean_bit="spoken vs fresh align · hot|thin",
    ) == (33, "wide", "align · wide", True)
    assert chart_price_bars_spoken_vs_fresh_delta(
        20.0,
        80.0,
        lean_bit="spoken vs fresh align · quiet|strong",
    ) == (-60, "wide", "align · wide", False)
    assert chart_price_bars_spoken_vs_fresh_delta(
        55.0,
        45.0,
        lean_bit="spoken vs fresh align · hot|thin",
    ) == (10, "", "clash · lean · Δ mid", True)
    assert chart_price_bars_spoken_vs_fresh_delta(
        66.7, 33.3, lean_bit=""
    ) == (None, "", "", False)
    assert (
        chart_price_bars_spoken_vs_fresh_delta_lead(
            33, "wide", lean_vs_delta="align · wide"
        )
        == "spoken"
    )
    assert (
        chart_price_bars_spoken_vs_fresh_delta_lead(
            -60, "wide", lean_vs_delta="align · wide"
        )
        == "fresh"
    )
    assert (
        chart_price_bars_spoken_vs_fresh_delta_lead(
            0, "thin", lean_vs_delta="align · thin"
        )
        == ""
    )
    assert (
        chart_price_bars_spoken_vs_fresh_delta_lead(
            10, "", lean_vs_delta="clash · lean · Δ mid"
        )
        == ""
    )
    assert (
        chart_price_bars_spoken_vs_fresh_delta_lead(
            33, "wide", lean_vs_delta=""
        )
        == ""
    )
    assert chart_price_bars_spoken_vs_fresh_delta_lead_size(
        66.7, 33.3, delta_lead="spoken"
    ) == (2.0, 66.7, 33.3)
    assert chart_price_bars_spoken_vs_fresh_delta_lead_size(
        20.0, 80.0, delta_lead="fresh"
    ) == (4.0, 80.0, 20.0)
    assert chart_price_bars_spoken_vs_fresh_delta_lead_size(
        75.0, 25.0, delta_lead=""
    ) == (None, None, None)
    assert chart_price_bars_spoken_vs_fresh_delta_lead_size(
        100.0, 0.0, delta_lead="spoken"
    ) == (None, None, None)
    assert chart_price_bars_vs_fresh(2, 1, 3) == (
        "vs 1 fresh · thin · 33.3%",
        1,
        33.3,
        "thin",
    )
    assert chart_price_bars_vs_fresh(1, 4, 5)[0] == "vs 4 fresh · strong · 80%"
    assert chart_price_bars_vs_fresh(3, 0, 3) == (
        "vs 0 fresh · thin · 0%",
        0,
        0.0,
        "thin",
    )
    assert chart_price_bars_vs_fresh(0, 2, 2) == ("", None, None, "")
    assert chart_price_bars_spoken_vs_fresh_lead(2, 1)[0] == "lead spoken · 67%"
    assert chart_price_bars_spoken_vs_fresh_lead(1, 2)[0] == "lead fresh · 67%"
    assert chart_price_bars_spoken_vs_fresh_sample_gap(1, 1) == (
        "spoken/fresh tied"
    )
    assert chart_price_bars_spoken_vs_fresh_lead(3, 0)[0] == ""
    assert chart_price_bars_lean_meta("") == "quiet"
    assert chart_price_bars_lean_meta(
        "vs 1 fresh · thin · 25% · lead spoken · 75% · lead stale · 67% · "
        "lead size · 2× · lead size sides · stale 2 · aging 1",
        warn=True,
    ).startswith("warn ·")

    quiet = chart_price_bars_glance(
        [
            {"bar_freshness": "aging"},
            {"bar_freshness": "fresh"},
            {"bar_freshness": "fresh"},
            {"bar_freshness": "fresh"},
            {"bar_freshness": "fresh"},
        ]
    )
    assert quiet["spoken_share_severity"] == "quiet"
    assert quiet["bit_core"] == "1 bars aging · quiet · 20%"
    assert quiet["line"] == quiet["bit_core"]
    assert "1 bars aging" in quiet["bit"]
    assert "quiet · 20%" in quiet["bit"]
    assert quiet["vs_fresh"] == "vs 4 fresh · strong · 80%"
    assert "vs 4 fresh · strong · 80%" in quiet["bit"]
    assert "vs 4 fresh · strong · 80%" in quiet["lean"]
    assert quiet["spoken_vs_fresh_lead"] == "lead fresh · 80%"
    assert "lead fresh · 80%" in quiet["bit"]
    assert quiet["spoken_vs_fresh_lead_size"] == 4.0
    assert quiet["spoken_vs_fresh_lead_size_louder"] == 4
    assert quiet["spoken_vs_fresh_lead_size_quieter"] == 1
    assert "sf size · 4×" in quiet["bit"]
    assert "sf size sides · fresh 4 · spoken 1" in quiet["bit"]
    assert quiet["spoken_vs_fresh_lean"] == (
        "spoken vs fresh align · quiet|strong"
    )
    assert quiet["spoken_vs_fresh_lean_warn"] is False
    assert "spoken vs fresh align · quiet|strong" in quiet["bit"]
    assert "spoken vs fresh align · quiet|strong" in quiet["lean"]
    # spoken 20 − fresh 80 → −60pp wide; quiet|strong stays calm (no Δ warn)
    assert quiet["spoken_vs_fresh_delta_pp"] == -60
    assert quiet["spoken_vs_fresh_delta_severity"] == "wide"
    assert quiet["spoken_vs_fresh_lean_vs_delta"] == "align · wide"
    assert quiet["spoken_vs_fresh_lean_vs_delta_warn"] is False
    assert "Δ wide · -60pp" in quiet["bit"]
    assert "lean vs Δ align · wide" in quiet["bit"]
    assert quiet["spoken_vs_fresh_delta_lead"] == "fresh"
    assert "Δ lead · fresh" in quiet["bit"]
    assert quiet["spoken_vs_fresh_delta_lead_size"] == 4.0
    assert quiet["spoken_vs_fresh_delta_lead_size_louder"] == 80.0
    assert quiet["spoken_vs_fresh_delta_lead_size_quieter"] == 20.0
    assert "Δ lead size · 4×" in quiet["bit"]
    assert "Δ lead size sides · fresh 80% · spoken 20%" in quiet["bit"]
    assert quiet["bit"].index("Δ lead · fresh") < quiet["bit"].index(
        "Δ lead size · 4×"
    )
    assert quiet["tone"] == "aging"
    assert quiet["lean_warn"] is False
    assert quiet["lean_meta"].startswith("quiet ·")
    assert "fresh lead" in quiet["lean_meta"]
    assert "sf size" in quiet["lean_meta"] or "sf sides" in quiet["lean_meta"]
    assert quiet["aging_stale_lead"] == ""
    assert quiet["aging_stale_lead_size"] is None


def test_charts_js_price_bars_lean_fold() -> None:
    """Charts must fold ownership/lead cascade under bars lean (desk fold parity)."""
    src = (
        Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "charts.js"
    ).read_text()
    assert "if (glance.lean)" in src
    assert "glance.lean_warn" in src
    assert "glance.lean_meta" in src
    assert '"price-bars-lean"' in src
    assert '"price-bars-lean-body"' in src
    assert "bars lean " in src
    assert "renderPriceBarsGlance" in src


def test_price_panels_speak_stale_last_bar(tmp_path: Path, monkeypatch):
    """Relative-price panels carry last-bar freshness (display only)."""
    from openbb_backend.charts import build_price_panels

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 90000,
                "holdings": {"AAPL": 5},
                "avg_buy_price": {"AAPL": 100},
            }
        )
    )
    (tmp_path / "archive").mkdir(parents=True)
    (tmp_path / "archive" / "opportunities_latest.json").write_text("{}")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "interval": "1d",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2026-10-01T00:00:00Z", "close": 100},
                    {"t": "2026-10-02T00:00:00Z", "close": 105},
                ],
            }
        )
    )
    panels = build_price_panels(tmp_path, live=False)
    assert len(panels) == 1
    assert panels[0]["last_bar"] == "2026-10-02"
    assert panels[0]["bar_freshness"] == "stale"
    assert panels[0]["bar_age_label"]


def test_price_history_skips_nan(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import fetch_price_history

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2026-07-01T00:00:00Z", "close": 100},
                    {"t": "2026-07-02T00:00:00Z", "close": float("nan")},
                    {"t": "2026-07-03T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    pts = fetch_price_history("AAPL", tmp_path, live=False)
    assert len(pts) == 2
    assert all(p["close"] == p["close"] for p in pts)  # no NaN


def test_price_history_lean_fallback_non_object_cache(tmp_path: Path, monkeypatch):
    """xang1234 #498: parseable non-object chart cache → empty, not crash."""
    from openbb_backend.charts import fetch_price_history

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text("[]\n")
    assert fetch_price_history("AAPL", tmp_path, live=False) == []
    (cache / "AAPL.json").write_text("null\n")
    assert fetch_price_history("AAPL", tmp_path, live=False) == []
    (cache / "MSFT.json").write_text('"oops"\n')
    assert fetch_price_history("MSFT", tmp_path, live=False) == []


def test_chart_cache_path_stays_under_chart_bars(tmp_path: Path):
    """xang1234 #498 / 464a0ce: refuse path-escape / junk chart cache tokens."""
    from openbb_backend.charts import _cache_path, fetch_price_history

    root = (tmp_path / "chart_bars").resolve()
    ok = _cache_path(tmp_path, "AAPL")
    assert ok is not None
    assert ok.is_relative_to(root)
    assert ok.name == "AAPL.json"

    slash = _cache_path(tmp_path, "BTC/USDT", interval="15m")
    assert slash is not None
    assert slash.name == "BTC_USDT_15m.json"
    assert slash.is_relative_to(root)

    assert _cache_path(tmp_path, "") is None
    assert _cache_path(tmp_path, "../etc/passwd") is None
    assert _cache_path(tmp_path, "..") is None
    assert _cache_path(tmp_path, "AAPL", interval="../x") is None
    assert fetch_price_history("../evil", tmp_path, live=False) == []
    assert fetch_price_history("", tmp_path, live=False) == []


def test_price_history_parses_advertised_points(tmp_path: Path, monkeypatch):
    """xang1234 c6f8650: truthy points blob ≠ hit — require list of point objects."""
    from openbb_backend.charts import fetch_price_history, _parse_chart_points

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    # Presence-only trap: points is a non-empty string.
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "interval": "1d",
                "fetched_at": 9e12,
                "points": "advertised",
            }
        )
    )
    assert fetch_price_history("AAPL", tmp_path, live=False) == []
    # Mixed junk in an advertised list — keep only real closes.
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "interval": "1d",
                "fetched_at": 9e12,
                "points": [
                    "junk",
                    {"t": "2026-07-01T00:00:00Z", "close": 100},
                    {"t": "2026-07-02T00:00:00Z"},
                    42,
                ],
            }
        )
    )
    pts = fetch_price_history("AAPL", tmp_path, live=False)
    assert pts == [{"t": "2026-07-01T00:00:00Z", "close": 100.0}]
    assert _parse_chart_points(None) == []
    assert _parse_chart_points({"close": 1}) == []


def test_unrealized_curve_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_unrealized_curve

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})  # 2024-07-20
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-20T00:00:00Z", "close": 100},
                    {"t": "2024-07-21T00:00:00Z", "close": 105},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_unrealized_curve(tmp_path, live=False)
    assert len(pts) >= 2
    assert pts[-1]["unrealized"] == 100.0  # 10 * (110-100)
    assert abs(pts[-1]["unrealized_pct"] - 10.0) < 1e-6
    payload = load_chart_payload(tmp_path)
    assert "unrealized" in payload


def test_from_buy_panel_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_from_buy_panels

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-19T00:00:00Z", "close": 90},
                    {"t": "2024-07-21T00:00:00Z", "close": 100},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    panels = build_from_buy_panels(tmp_path, live=False)
    assert panels
    aapl = next(p for p in panels if p["symbol"] == "AAPL")
    assert aapl["buy_price"] == 100
    assert aapl["points"][0]["rebased"] == 100
    assert aapl["change_pct"] == 10.0
    assert aapl["first_t"]
    assert aapl["last_t"]
    assert "span_hours" in aapl
    assert aapl["span_hours"] >= 0
    assert aapl["interval"] == "1d"


def test_hold_chart_interval_short_vs_long():
    from openbb_backend.charts import hold_chart_interval

    assert hold_chart_interval(7.0, is_crypto=True) == "15m"
    assert hold_chart_interval(48.0, is_crypto=True) == "1h"
    assert hold_chart_interval(200.0, is_crypto=False) == "1d"


def test_from_buy_short_crypto_uses_intraday_cache(tmp_path: Path, monkeypatch):
    """Short holds must not collapse to buy→now when only daily bars exist."""
    import time
    from datetime import datetime, timedelta, timezone

    from openbb_backend.charts import build_from_buy_panels

    buy_ts = time.time() - 7 * 3600
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 90000,
                "holdings": {"BTC-USD": 0.1},
                "avg_buy_price": {"BTC-USD": 64000},
                "total_fees_paid": 1,
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("")
    (tmp_path / "entry_times.json").write_text(json.dumps({"BTC-USD": buy_ts}))
    (tmp_path / "archive").mkdir(parents=True, exist_ok=True)
    (tmp_path / "archive" / "opportunities_latest.json").write_text("{}")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    t0 = datetime.fromtimestamp(buy_ts, tz=timezone.utc)
    pts = []
    for i in range(0, 8 * 4):
        ts = t0 + timedelta(minutes=15 * i)
        pts.append(
            {
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "close": 64000 + (i % 5) * 40 - 20,
            }
        )
    (cache / "BTC-USD_15m.json").write_text(
        json.dumps(
            {
                "symbol": "BTC-USD",
                "interval": "15m",
                "fetched_at": 9e12,
                "points": pts,
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    panels = build_from_buy_panels(tmp_path, live=False)
    btc = next(p for p in panels if p["symbol"] == "BTC-USD")
    assert btc["interval"] == "15m"
    assert len(btc["points"]) > 5


def test_charts_js_universe_mix_lean_fold() -> None:
    """Charts must fold timeout↔inflight mix the same way the desk template does."""
    src = (
        Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "charts.js"
    ).read_text()
    assert "glance.mix_lean" in src
    assert "glance.mix_lean_warn" in src
    assert "glance.mix_lean_meta" in src
    assert "glance.error_lean_meta" in src
    assert "glance.streak_lean_meta" in src
    assert '"universe-mix-lean"' in src
    assert '"universe-mix-lean-body"' in src
    mix_at = src.find('"universe-mix-lean"')
    error_at = src.find('"universe-error-lean"')
    streak_at = src.find('"universe-streak-lean"')
    assert 0 < mix_at < error_at < streak_at


def test_charts_js_equity_hours_inactive_fold_meta() -> None:
    """Charts must name why the Hours inactive fold opened (desk macros parity)."""
    src = (
        Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "charts.js"
    ).read_text()
    assert "glance.inactive_meta" in src
    assert "glance.inactive_warn" in src
    assert "equity-hours-inactive-body" in src
    macro = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "templates"
        / "macros.html"
    ).read_text()
    assert "inactive_meta" in macro
    assert "equity-hours-inactive-body" in macro


def test_charts_js_escapes_tip_free_text() -> None:
    """tradermonty #440 — tip.innerHTML must escape symbol/name/label."""
    src = (Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "charts.js").read_text()
    assert "function escapeHtml(s)" in src
    assert "escapeHtml(d.label)" in src
    assert "escapeHtml(panel.symbol)" in src
    assert "escapeHtml(panel.name)" in src
    # Relative tip must not concatenate raw panel fields into tip HTML.
    assert 'panel.symbol +\n        "</strong>"' not in src
    assert "panel.name + \"</span>\"" not in src
    assert 'panel.name + "</span>"' not in src

    def escape_html(s: object) -> str:
        return (
            str("" if s is None else s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    assert escape_html('<img src=x onerror=alert(1)>') == (
        "&lt;img src=x onerror=alert(1)&gt;"
    )
    assert escape_html("ACME & Co \"A\"") == "ACME &amp; Co &quot;A&quot;"


def test_chart_payload_falls_back_when_latest_missing(tmp_path: Path, monkeypatch):
    """Charts keep-newest parity with desk (xang1234 #682/#685)."""
    from openbb_backend.charts import _load_opportunities

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    arch = tmp_path / "archive"
    (arch / "opportunities_latest.json").unlink()
    (arch / "opportunities_20260201_120000.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-10-25T11:00:00+00:00",
                "stock_breakouts": [{"symbol": "NVDA", "price": 100.0}],
            }
        )
    )

    opp, pin = _load_opportunities(tmp_path)
    assert pin["pin"] == "missing"
    assert pin["fallback"] is True
    assert pin["healed"] is True
    assert "latest missing · healed" in pin["bit"]
    assert opp.get("scan_time") == "2026-10-25T11:00:00+00:00"
    assert opp["stock_breakouts"][0]["symbol"] == "NVDA"
    # Resolve heals the pin — next Charts open is quiet for hard-readers.
    payload = load_chart_payload(tmp_path)
    sf = payload["scan_freshness"]
    assert sf["archive_pin"] == "latest"
    assert sf.get("archive_pin_bit") in ("", None)


def test_chart_payload_falls_back_when_latest_stale(tmp_path: Path, monkeypatch):
    """Live latest behind a newer publish → Charts reads newest + heals pin."""
    from openbb_backend.charts import _load_opportunities

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    arch = tmp_path / "archive"
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text(json.dumps({"scan_time": "2026-01-01T12:00:00+00:00"}))
    (arch / "opportunities_20260201_120000.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-10-25T11:30:00+00:00",
                "stock_breakouts": [{"symbol": "MSFT", "price": 400.0}],
            }
        )
    )
    (arch / "opportunities_latest.json").unlink()
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    opp, pin = _load_opportunities(tmp_path)
    assert pin["pin"] == "stale"
    assert pin["behind"] == 1
    assert pin["healed"] is True
    assert opp["stock_breakouts"][0]["symbol"] == "MSFT"
    assert (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag 31d · stale · "
        "lag/share clash · stale · hot · "
        "lag/share vs lean align · both clash · "
        "lag/share↔lean vs lean↔Δ align · both align · healed"
    ) in pin["bit"]

    # After heal, payload resolve is keep-newest clean.
    payload = load_chart_payload(tmp_path)
    sf = payload["scan_freshness"]
    assert sf["archive_pin"] == "latest"
    assert opp["stock_breakouts"][0]["symbol"] == "MSFT"
