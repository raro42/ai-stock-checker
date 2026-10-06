"""Offline tests for LAYA / JEV System-1 advisory (fail-open, not a gate)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_laya_glance
from stock_checker.laya_decision import (
    PAPER_ENTRY_QUESTIONS,
    build_paper_entry_state,
    evaluate_paper_entry,
    laya_advisory_enabled,
    laya_configured,
    maybe_advise_paper_entry,
    parse_system_one_answers,
    record_laya_decision,
    summarize_laya_decisions,
)


def test_paper_entry_questions_shape() -> None:
    assert PAPER_ENTRY_QUESTIONS["entry"]["type"] == "choice"
    assert set(PAPER_ENTRY_QUESTIONS["entry"]["criteria"]) == {
        "pass",
        "hold",
        "reject",
    }
    assert PAPER_ENTRY_QUESTIONS["edge"]["type"] == "score"
    assert PAPER_ENTRY_QUESTIONS["fee_churn"]["type"] == "noul"


def test_build_state_includes_symbol() -> None:
    text = build_paper_entry_state(
        {
            "symbol": "AAPL",
            "name": "Apple",
            "current_price": 200,
            "previous_close": 198,
            "strategy": "breakout",
        }
    )
    assert "AAPL" in text
    assert "breakout" in text
    assert "anti-churn" in text or "min hold" in text.lower() or "24h" in text


def test_parse_system_one_answers() -> None:
    parsed = parse_system_one_answers(
        {
            "answers": {
                "entry": {
                    "choice": "pass",
                    "probabilities": {"pass": 0.7, "hold": 0.2, "reject": 0.1},
                },
                "edge": {"score": 2.1},
                "fee_churn": {"noul": 0.15},
            }
        }
    )
    assert parsed["entry"] == "pass"
    assert parsed["probabilities"]["pass"] == 0.7
    assert parsed["edge_score"] == 2.1
    assert parsed["fee_churn"] == 0.15


def test_evaluate_fail_open_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    monkeypatch.delenv("LAYA_ADVISORY", raising=False)
    assert not laya_configured()
    res = evaluate_paper_entry({"symbol": "MSFT"})
    assert res["fail_open"] is True
    assert res["ok"] is False
    assert res["reason"] == "not_configured"


def test_evaluate_advisory_off_when_url_set(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("LAYA_ADVISORY", "0")
    assert laya_configured()
    assert not laya_advisory_enabled()
    res = evaluate_paper_entry({"symbol": "MSFT"})
    assert res["reason"] == "advisory_off"
    assert res["fail_open"] is True


def test_evaluate_with_transport(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def fake_transport(url, body, headers, timeout):
        assert url.endswith("/v1/systemone")
        assert "questions" in body
        assert body["questions"]["entry"]["type"] == "choice"
        return {
            "answers": {
                "entry": {
                    "choice": "hold",
                    "probabilities": {"pass": 0.2, "hold": 0.7, "reject": 0.1},
                },
                "edge": {"score": 1.0},
                "fee_churn": {"noul": 0.4},
            }
        }

    res = evaluate_paper_entry(
        {"symbol": "SAP.DE", "current_price": 100, "previous_close": 99},
        transport=fake_transport,
    )
    assert res["ok"] is True
    assert res["fail_open"] is False
    assert res["entry"] == "hold"
    assert res["latency_ms"] is not None


def test_evaluate_transport_error_fail_open(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def boom(*_a, **_k):
        raise TimeoutError("slow")

    res = evaluate_paper_entry({"symbol": "X"}, transport=boom)
    assert res["ok"] is False
    assert res["fail_open"] is True
    assert "provider_error" in res["reason"]


def test_record_and_summarize(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def ok_transport(*_a, **_k):
        return {
            "answers": {
                "entry": {"choice": "pass", "probabilities": {"pass": 0.9}},
                "edge": {"score": 2.5},
                "fee_churn": {"noul": 0.05},
            }
        }

    res = maybe_advise_paper_entry(
        {"symbol": "BTC-USD"}, tmp_path, transport=ok_transport
    )
    assert res is not None
    assert res["entry"] == "pass"
    stats = summarize_laya_decisions(tmp_path)
    assert stats["count"] == 1
    assert stats["pass"] == 1
    assert stats["newest"]["symbol"] == "BTC-USD"


def test_laya_glance_off(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    monkeypatch.delenv("LAYA_ADVISORY", raising=False)
    g = build_laya_glance(tmp_path)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "not a gate" in g["line"]


def test_laya_glance_advisory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    record_laya_decision(
        tmp_path,
        {
            "ok": True,
            "fail_open": False,
            "reason": "ok",
            "entry": "reject",
            "edge_score": 0.5,
            "fee_churn": 0.8,
            "latency_ms": 40,
            "model": "systemone",
        },
        symbol="NVDA",
    )
    g = build_laya_glance(tmp_path)
    assert g["advisory"] is True
    assert g["tone"] == "advisory"
    assert g["freshness"] == "fresh"
    assert "NVDA" in g["line"]
    assert "reject" in g["line"]
    assert "fresh" in g["line"]
    assert g["line"].index("fresh") < g["line"].index("NVDA")


def test_laya_glance_stale_last_row(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=10)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(tmp_path, scan_interval_sec=900)
    assert g["freshness"] == "stale"
    assert g["tone"] == "stale"
    assert "stale" in g["line"]
    assert "MSFT" in g["line"]


def test_laya_glance_scan_clash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=scan_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_laya_clash"] == "clash · scan fresh"
    assert "clash" in g["line"]
    assert g["line"].index("stale") < g["line"].index("clash")
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert same["scan_vs_laya_clash"] == ""
    assert "clash" not in same["line"]


def test_laya_glance_debate_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-row band ≠ last-debate band → clash · debate {tone} (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(
            {
                "updated_at": fresh_at,
                "events": [
                    {
                        "at": fresh_at,
                        "symbol": "NVDA",
                        "action": "BUY",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "stale"
    assert g["debate_freshness"] == "fresh"
    assert g["scan_vs_laya_clash"] == "clash · debate fresh"
    assert "clash" in g["line"]
    both = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert both["scan_vs_laya_clash"] == "clash · scan fresh · debate fresh"
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(
            {
                "updated_at": stale_at,
                "events": [{"at": stale_at, "symbol": "NVDA", "action": "HOLD"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    quiet = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert quiet["scan_vs_laya_clash"] == ""
    assert same["scan_vs_laya_clash"] == "clash · debate fresh"


def test_desk_templates_include_laya_glance() -> None:
    roots = Path("openbb_backend/templates")
    for name in (
        "desk_overview.html",
        "desk_ops.html",
        "desk_ideas.html",
        "desk_screener.html",
        "desk_book.html",
        "desk_breadth.html",
        "desk_scan_log.html",
    ):
        text = (roots / name).read_text()
        assert "laya_glance" in text, name
    assert "laya_glance" in Path("openbb_backend/templates/macros.html").read_text()
    assert "renderLayaGlance" in Path("openbb_backend/static/charts.js").read_text()


def test_laya_glance_no_sample(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    g = build_laya_glance(tmp_path)
    assert "no sample" in g["line"]
    assert g["tone"] == "advisory"
    assert g["freshness"] == ""


def test_laya_glance_in_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    from openbb_backend.desk import load_desk_snapshot

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert "laya_glance" in snap
    assert snap["laya_glance"]["ready"] is True
